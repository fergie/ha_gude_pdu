"""API client for GUDE PDU devices."""  # codespell:ignore gude
# Based on https://wiki.gude-systems.com/EPC_HTTP_Interface

import base64
from dataclasses import dataclass, field
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import COMPONENTS_ALL

_LOGGER = logging.getLogger(__name__)


class GudeError(Exception):
    """Base exception for errors."""


class GudeConnectionError(GudeError):
    """Exception raised when a connection error occurs."""


class GudeAuthError(GudeError):
    """Exception raised when authentication fails."""


@dataclass(slots=True, frozen=True)
class GudeDeviceInfo:
    """Device metadata retrieved from PDU."""

    mac: str
    product_name: str
    vendor_name: str
    firmware_version: str
    hostname: str


@dataclass(slots=True, frozen=True)
class GudeOutlet:
    """Represents a switchable outlet port on a PDU."""

    index: int  # 1-based index (p=1..N)
    name: str
    state: bool
    type: int


@dataclass(slots=True, frozen=True)
class GudeSensorValue:
    """Represents a measured sensor or telemetry value."""

    sensor_id: str
    name: str
    value: float | int | str | None
    unit: str | None
    precision: int | None
    sensor_type: int
    property_id: str
    field_name: str


@dataclass(slots=True)
class GudeStatus:
    """Complete status data model from a PDU."""

    device_info: GudeDeviceInfo
    outputs: dict[int, GudeOutlet] = field(default_factory=dict)
    sensors: dict[str, GudeSensorValue] = field(default_factory=dict)
    raw_data: dict[str, Any] = field(default_factory=dict)


def _slugify(text: str) -> str:
    """Convert text into a sanitized identifier slug."""
    for char in (" ", "-", "/", ":", ".", "(", ")", "[", "]"):
        text = text.replace(char, "_")
    return "_".join(part for part in text.lower().split("_") if part)


class GudeClient:
    """Asynchronous HTTP/CGI API client for PDU devices."""

    def __init__(
        self,
        host: str,
        port: int,
        ssl: bool,
        verify_ssl: bool,
        session: ClientSession,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Initialise the client."""
        self.host = host
        self.port = port
        self.ssl = ssl
        self.verify_ssl = verify_ssl
        self.session = session
        self.username = username
        self.password = password
        self.timeout = ClientTimeout(total=timeout)
        self._session_id_x: str | None = None
        self._cookies: dict[str, str] = {}
        self._legacy_endpoint: bool = False

    @property
    def base_url(self) -> str:
        """Return the base URL for the device."""
        scheme = "https" if self.ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def _headers(self) -> dict[str, str]:
        """Return headers with Basic Auth and session tokens if available."""
        headers: dict[str, str] = {}
        if self.username or self.password:
            user_pass = f"{self.username or ''}:{self.password or ''}".encode()
            headers["Authorization"] = f"Basic {base64.b64encode(user_pass).decode()}"
        if self._session_id_x:
            headers["sessionidX"] = self._session_id_x
        if self._cookies:
            headers["Cookie"] = "; ".join(
                f"{key}={val}" for key, val in self._cookies.items()
            )
        return headers

    async def _login(self) -> None:
        """Authenticate using session login (/login.json)."""
        self._cookies.clear()
        self._session_id_x = None
        if not (self.username or self.password):
            raise GudeAuthError("Authentication failed: invalid credentials")

        url = f"{self.base_url}/login.json"
        async with self.session.post(
            url,
            data={
                "username": self.username or "",
                "password": self.password or "",
            },
            ssl=self.verify_ssl,
            timeout=self.timeout,
        ) as response:
            if response.status == 401:
                raise GudeAuthError("Authentication failed: invalid credentials")
            if response.status != 200:
                raise GudeError(f"Unexpected HTTP status {response.status}")
            for key, morsel in response.cookies.items():
                self._cookies[key] = morsel.value
            text = await response.text()
            data: dict[str, Any] = json.loads(text)

        if not data.get("login"):
            raise GudeAuthError("Authentication failed: invalid credentials")

        session_id_x = data.get("sessionidX")
        self._session_id_x = str(session_id_x) if session_id_x else None

    async def _get_status_json(self, params: dict[str, Any]) -> dict[str, Any]:
        """Perform a GET request to status.json (with fallback to statusjsn.js)."""
        endpoint = "statusjsn.js" if self._legacy_endpoint else "status.json"
        url = f"{self.base_url}/{endpoint}"
        async with self.session.get(
            url,
            params=params,
            headers=self._headers,
            ssl=self.verify_ssl,
            timeout=self.timeout,
        ) as response:
            if not self._legacy_endpoint and response.status in (404, 405):
                self._legacy_endpoint = True
                return await self._get_status_json(params)
            if response.status == 401:
                raise GudeAuthError("Authentication failed: invalid credentials")
            if response.status != 200:
                raise GudeError(f"Unexpected HTTP status {response.status}")
            text = await response.text()
            result: dict[str, Any] = json.loads(text)
            return result

    async def _post_status_json(self, params: dict[str, Any]) -> dict[str, Any]:
        """Perform a POST request to status.json (with fallback to statusjsn.js)."""
        if self._legacy_endpoint:
            return await self._get_status_json(params)

        url = f"{self.base_url}/status.json"
        async with self.session.post(
            url,
            data={key: str(val) for key, val in params.items()},
            headers=self._headers,
            ssl=self.verify_ssl,
            timeout=self.timeout,
            allow_redirects=False,
        ) as response:
            if response.status in (404, 405):
                self._legacy_endpoint = True
                return await self._get_status_json(params)
            if response.status == 401:
                raise GudeAuthError("Authentication failed: invalid credentials")
            if response.status in (302, 307):
                return {"authreq": 1}
            if response.status != 200:
                raise GudeError(f"Unexpected HTTP status {response.status}")
            text = await response.text()
            result: dict[str, Any] = json.loads(text)
            return result

    async def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send a request to the device and return parsed JSON."""
        request_fn = (
            self._post_status_json if "cmd" in params else self._get_status_json
        )
        try:
            data = await request_fn(params)
            if data.get("authreq"):
                await self._login()
                data = await request_fn(params)
        except ClientResponseError as err:
            if err.status == 401:
                raise GudeAuthError(
                    "Authentication failed: invalid credentials"
                ) from err
            raise GudeConnectionError(
                f"HTTP error communicating with PDU: {err}"
            ) from err
        except ClientError as err:
            raise GudeConnectionError(f"Connection error with PDU: {err}") from err
        except TimeoutError as err:
            raise GudeConnectionError(f"Timeout communicating with PDU: {err}") from err
        except (json.JSONDecodeError, ValueError) as err:
            raise GudeError(f"Invalid JSON returned by PDU: {err}") from err

        if data.get("authreq"):
            raise GudeAuthError("Authentication failed: invalid credentials")
        return data

    async def authenticate(self) -> GudeDeviceInfo:
        """Validate credentials and retrieve device metadata."""
        # Query outputs (1) + ethernet (8) + misc (16)
        data = await self._request({"components": 25})
        device_info = self._parse_device_info(data)
        if not device_info.mac:
            raise GudeError("PDU did not return a device MAC address")
        return device_info

    def _parse_device_info(self, data: dict[str, Any]) -> GudeDeviceInfo:
        """Extract device metadata from raw status JSON."""
        misc: dict[str, Any] = data.get("misc", {})
        ethernet: dict[str, Any] = data.get("ethernet", {})

        mac = ethernet.get("mac", "")
        product_name = misc.get("product_name", "GUDE PDU")  # codespell:ignore gude
        vendor_name = misc.get("vendor_name", "GUDE Systems")  # codespell:ignore gude
        firmware_version = misc.get("firm_v", "unknown")
        hostname = misc.get("hostname") or misc.get("def_hostname") or product_name

        return GudeDeviceInfo(
            mac=mac,
            product_name=product_name,
            vendor_name=vendor_name,
            firmware_version=firmware_version,
            hostname=hostname,
        )

    def _parse_outputs(self, data: dict[str, Any]) -> dict[int, GudeOutlet]:
        """Extract switchable outlets from raw JSON."""
        outputs_list = data.get("outputs")
        if not isinstance(outputs_list, list):
            return {}

        outputs: dict[int, GudeOutlet] = {}
        for idx, out in enumerate(outputs_list, start=1):
            if not isinstance(out, dict):
                continue
            name = out.get("name") or f"Port {idx}"
            state = bool(out.get("state", 0))
            out_type = int(out.get("type", 1))
            outputs[idx] = GudeOutlet(
                index=idx,
                name=name,
                state=state,
                type=out_type,
            )
        return outputs

    @staticmethod
    def _find_matching_val_item(
        sensor_values: list[Any], index: int, sensor_type: int
    ) -> dict[str, Any] | None:
        """Locate matching sensor_values entry for a given sensor type."""
        if (
            index < len(sensor_values)
            and isinstance(item := sensor_values[index], dict)
            and item.get("type") == sensor_type
        ):
            return item
        for candidate in sensor_values:
            if isinstance(candidate, dict) and candidate.get("type") == sensor_type:
                return candidate
        return None

    @staticmethod
    def _parse_simple_sensors(
        descr: dict[str, Any],
        val_item: dict[str, Any] | None,
        sensor_type: int,
        sensors: dict[str, GudeSensorValue],
    ) -> None:
        """Parse simple sensors having fields and properties."""
        fields = descr.get("fields")
        properties = descr.get("properties")
        if not isinstance(fields, list) or not isinstance(properties, list):
            return

        raw_values = val_item.get("values", []) if val_item else []

        for prop_idx, prop in enumerate(properties):
            if not isinstance(prop, dict):
                continue
            prop_id = str(prop.get("id", prop_idx))
            prop_vals = (
                raw_values[prop_idx]
                if prop_idx < len(raw_values) and isinstance(raw_values[prop_idx], list)
                else []
            )

            for field_idx, fld in enumerate(fields):
                if not isinstance(fld, dict):
                    continue
                field_name = fld.get("name", f"Field_{field_idx}")
                unit = fld.get("unit")
                precision = fld.get("decPrecision")

                raw_v_dict = (
                    prop_vals[field_idx]
                    if field_idx < len(prop_vals)
                    and isinstance(prop_vals[field_idx], dict)
                    else None
                )
                val = raw_v_dict.get("v") if raw_v_dict is not None else None

                sensor_id = _slugify(f"{sensor_type}_{prop_id}_{field_name}")
                display_name = f"{prop_id} {field_name}" if prop_id else field_name

                sensors[sensor_id] = GudeSensorValue(
                    sensor_id=sensor_id,
                    name=display_name,
                    value=val,
                    unit=unit,
                    precision=precision,
                    sensor_type=sensor_type,
                    property_id=prop_id,
                    field_name=field_name,
                )

    @staticmethod
    def _parse_sub_groups(
        group_defs: list[Any],
        prop_groups_meta: list[Any],
        prop_groups_data: list[Any],
        sensor_type: int,
        prop_id: str,
        sensors: dict[str, GudeSensorValue],
    ) -> None:
        """Parse subgroup fields within a group."""
        for group_idx, group_def in enumerate(group_defs):
            if not isinstance(group_def, dict):
                continue
            fields = group_def.get("fields", [])
            if not isinstance(fields, list):
                continue

            sub_props = (
                prop_groups_meta[group_idx]
                if group_idx < len(prop_groups_meta)
                and isinstance(prop_groups_meta[group_idx], list)
                else []
            )
            sub_vals_list = (
                prop_groups_data[group_idx]
                if group_idx < len(prop_groups_data)
                and isinstance(prop_groups_data[group_idx], list)
                else []
            )

            for sub_idx, sub_prop in enumerate(sub_props):
                if not isinstance(sub_prop, dict):
                    continue
                sub_id = str(sub_prop.get("id", sub_idx))
                field_vals = (
                    sub_vals_list[sub_idx]
                    if sub_idx < len(sub_vals_list)
                    and isinstance(sub_vals_list[sub_idx], list)
                    else []
                )

                for field_idx, fld in enumerate(fields):
                    if not isinstance(fld, dict):
                        continue
                    field_name = fld.get("name", f"Field_{field_idx}")
                    unit = fld.get("unit")
                    precision = fld.get("decPrecision")

                    raw_v_dict = (
                        field_vals[field_idx]
                        if field_idx < len(field_vals)
                        and isinstance(field_vals[field_idx], dict)
                        else None
                    )
                    val = raw_v_dict.get("v") if raw_v_dict is not None else None

                    sensor_id = _slugify(
                        f"{sensor_type}_{prop_id}_{sub_id}_{field_name}"
                    )
                    parts = [p for p in (prop_id, sub_id, field_name) if p]
                    display_name = " ".join(parts)

                    sensors[sensor_id] = GudeSensorValue(
                        sensor_id=sensor_id,
                        name=display_name,
                        value=val,
                        unit=unit,
                        precision=precision,
                        sensor_type=sensor_type,
                        property_id=f"{prop_id}_{sub_id}",
                        field_name=field_name,
                    )

    @staticmethod
    def _parse_group_sensors(
        descr: dict[str, Any],
        val_item: dict[str, Any] | None,
        sensor_type: int,
        sensors: dict[str, GudeSensorValue],
    ) -> None:
        """Parse complex sensor groups."""
        group_defs = descr.get("groups")
        properties = descr.get("properties")
        if not isinstance(group_defs, list) or not isinstance(properties, list):
            return

        raw_values = val_item.get("values", []) if val_item else []

        for prop_idx, prop in enumerate(properties):
            if not isinstance(prop, dict):
                continue
            prop_id = str(prop.get("id", prop_idx))
            prop_groups_meta = prop.get("groups", [])
            prop_groups_data = (
                raw_values[prop_idx]
                if prop_idx < len(raw_values) and isinstance(raw_values[prop_idx], list)
                else []
            )

            GudeClient._parse_sub_groups(
                group_defs,
                prop_groups_meta,
                prop_groups_data,
                sensor_type,
                prop_id,
                sensors,
            )

    def _parse_sensors(self, data: dict[str, Any]) -> dict[str, GudeSensorValue]:
        """Extract dynamic sensors from sensor_descr and sensor_values."""
        sensor_descr = data.get("sensor_descr")
        sensor_values = data.get("sensor_values")
        if not isinstance(sensor_descr, list) or not isinstance(sensor_values, list):
            return {}

        sensors: dict[str, GudeSensorValue] = {}

        for i, descr in enumerate(sensor_descr):
            if not isinstance(descr, dict):
                continue
            sensor_type = descr.get("type")
            if sensor_type is None:
                continue

            val_item = self._find_matching_val_item(sensor_values, i, sensor_type)

            if "fields" in descr and "properties" in descr:
                self._parse_simple_sensors(descr, val_item, sensor_type, sensors)
            elif "groups" in descr and "properties" in descr:
                self._parse_group_sensors(descr, val_item, sensor_type, sensors)

        return sensors

    async def get_status(self, components: int = COMPONENTS_ALL) -> GudeStatus:
        """Fetch status and sensor data from the PDU."""
        data = await self._request({"components": components})
        device_info = self._parse_device_info(data)
        outputs = self._parse_outputs(data)
        sensors = self._parse_sensors(data)

        return GudeStatus(
            device_info=device_info,
            outputs=outputs,
            sensors=sensors,
            raw_data=data,
        )

    async def set_outlet_state(self, port: int, state: bool) -> bool:
        """Set the power state of an outlet port (1-based index)."""
        data = await self._request(
            {
                "components": 1,
                "cmd": 1,
                "p": port,
                "s": 1 if state else 0,
            }
        )
        outputs = self._parse_outputs(data)
        outlet = outputs.get(port)
        if outlet is not None:
            return outlet.state
        return state
