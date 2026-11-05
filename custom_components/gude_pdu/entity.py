"""Base entity for the GUDE PDU integration."""  # codespell:ignore gude

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GudeConfigEntry, GudeDataUpdateCoordinator


class GudeEntity(CoordinatorEntity[GudeDataUpdateCoordinator]):
    """Base class for PDU entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GudeDataUpdateCoordinator,
        entry: GudeConfigEntry,
        port_index: int | None = None,
    ) -> None:
        """Initialise the base entity."""
        super().__init__(coordinator)
        device_info = coordinator.data.device_info
        formatted_mac = dr.format_mac(device_info.mac)
        parent_device_info = DeviceInfo(
            configuration_url=coordinator.client.base_url,
            connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)},
            identifiers={(DOMAIN, formatted_mac)},
            manufacturer=device_info.vendor_name,
            model=device_info.product_name,
            name=device_info.hostname or device_info.product_name,
            sw_version=device_info.firmware_version,
        )
        if port_index is not None:
            parent_device = dr.async_get(
                coordinator.hass
            ).async_get_or_create_from_info(
                config_entry_id=entry.entry_id,
                device_info=parent_device_info,
            )
            self._attr_device_info = ChildDeviceInfo(
                identifiers={(DOMAIN, f"{formatted_mac}_port_{port_index}")},
                parent_device_id=parent_device.id,
                translation_key="outlet",
                translation_placeholders={"port": str(port_index)},
            )
        else:
            self._attr_device_info = parent_device_info
