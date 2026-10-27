"""Switch platform for GUDE PDU power outlets."""  # codespell:ignore gude

from typing import Any, override

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import GudeConnectionError, GudeError
from .const import DOMAIN
from .coordinator import GudeConfigEntry, GudeDataUpdateCoordinator
from .entity import GudeEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GudeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PDU outlet switches."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        GudeOutletSwitch(coordinator, entry, port_idx)
        for port_idx in coordinator.data.outputs
    )


class GudeOutletSwitch(GudeEntity, SwitchEntity):
    """Switch entity representing a PDU power outlet."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_translation_key = "outlet"

    def __init__(
        self,
        coordinator: GudeDataUpdateCoordinator,
        entry: GudeConfigEntry,
        port_index: int,
    ) -> None:
        """Initialise the outlet switch."""
        super().__init__(coordinator, entry)
        self.port_index = port_index
        formatted_mac = dr.format_mac(coordinator.data.device_info.mac)
        self._attr_unique_id = f"{formatted_mac}_port_{port_index}"
        self._attr_translation_placeholders = {"port": str(port_index)}

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        outlet = self.coordinator.data.outputs.get(self.port_index)
        if outlet is not None:
            return outlet.state
        return None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the outlet on."""
        try:
            await self.coordinator.client.set_outlet_state(self.port_index, True)
        except (GudeConnectionError, GudeError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_failed",
                translation_placeholders={
                    "port": str(self.port_index),
                    "error": str(err),
                },
            ) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the outlet off."""
        try:
            await self.coordinator.client.set_outlet_state(self.port_index, False)
        except (GudeConnectionError, GudeError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_failed",
                translation_placeholders={
                    "port": str(self.port_index),
                    "error": str(err),
                },
            ) from err
        await self.coordinator.async_request_refresh()
