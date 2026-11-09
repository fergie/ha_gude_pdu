"""DataUpdateCoordinator for the GUDE PDU integration."""  # codespell:ignore gude

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GudeAuthError,
    GudeClient,
    GudeConnectionError,
    GudeError,
    GudeStatus,
)
from .const import (
    CONF_USE_OUTLET_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USE_OUTLET_NAMES,
    DOMAIN,
    LOGGER,
)


@dataclass
class GudeData:
    """Runtime data stored in the config entry."""

    coordinator: GudeDataUpdateCoordinator
    client: GudeClient


type GudeConfigEntry = ConfigEntry[GudeData]


class GudeDataUpdateCoordinator(DataUpdateCoordinator[GudeStatus]):
    """Class to manage fetching PDU data from the device."""

    config_entry: GudeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GudeConfigEntry,
        client: GudeClient,
    ) -> None:
        """Initialise the coordinator."""
        self.client = client
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{client.host}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    @callback
    def async_update_outlet_device_names(
        self, status: GudeStatus | None = None
    ) -> None:
        """Update outlet child device names when configured to use API names."""
        if not self.config_entry.data.get(
            CONF_USE_OUTLET_NAMES, DEFAULT_USE_OUTLET_NAMES
        ):
            return

        data = status if status is not None else self.data
        device_registry = dr.async_get(self.hass)
        formatted_mac = dr.format_mac(data.device_info.mac)

        for port_index, outlet in data.outputs.items():
            identifier = (DOMAIN, f"{formatted_mac}_port_{port_index}")
            child_device = device_registry.async_get_child_device_by_identifier(
                identifier=identifier,
                config_entry_id=self.config_entry.entry_id,
            )
            if child_device is None:
                continue

            if outlet.name:
                device_info = ChildDeviceInfo(
                    identifiers={identifier},
                    parent_device_id=child_device.parent_device_id,
                    name=f"{port_index}: {outlet.name}",
                )
            else:
                device_info = ChildDeviceInfo(
                    identifiers={identifier},
                    parent_device_id=child_device.parent_device_id,
                    translation_key="outlet",
                    translation_placeholders={"port": str(port_index)},
                )

            device_registry.async_get_or_create_child_from_info(
                config_entry_id=self.config_entry.entry_id,
                device_info=device_info,
            )

    @override
    async def _async_update_data(self) -> GudeStatus:
        """Fetch status data from the device."""
        try:
            status = await self.client.get_status()
        except GudeAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except (GudeConnectionError, GudeError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        if self.data is not None:
            self.async_update_outlet_device_names(status)
        return status
