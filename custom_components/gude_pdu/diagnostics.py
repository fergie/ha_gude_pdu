"""Diagnostics support for GUDE PDU."""  # codespell:ignore gude

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import GudeConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GudeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "device_info": {
            "mac": "**REDACTED**",
            "product_name": coordinator.data.device_info.product_name,
            "vendor_name": coordinator.data.device_info.vendor_name,
            "firmware_version": coordinator.data.device_info.firmware_version,
            "hostname": coordinator.data.device_info.hostname,
        },
        "outputs": {
            idx: {
                "name": out.name,
                "state": out.state,
                "type": out.type,
            }
            for idx, out in coordinator.data.outputs.items()
        },
        "sensors": {
            k: {
                "name": v.name,
                "value": v.value,
                "unit": v.unit,
                "precision": v.precision,
                "sensor_type": v.sensor_type,
            }
            for k, v in coordinator.data.sensors.items()
        },
        "raw_data": async_redact_data(coordinator.data.raw_data, TO_REDACT),
    }
