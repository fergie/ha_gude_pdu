"""Base entity for the GUDE PDU integration."""  # codespell:ignore gude

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
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
    ) -> None:
        """Initialise the base entity."""
        super().__init__(coordinator)
        device_info = coordinator.data.device_info
        formatted_mac = dr.format_mac(device_info.mac)
        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.client.base_url,
            connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)},
            identifiers={(DOMAIN, formatted_mac)},
            manufacturer=device_info.vendor_name,
            model=device_info.product_name,
            name=device_info.hostname or device_info.product_name,
            sw_version=device_info.firmware_version,
        )
