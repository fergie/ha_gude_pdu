"""Test GUDE PDU switch platform."""  # codespell:ignore gude

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gude_pdu.api import GudeClient, GudeConnectionError
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entities are created with correct states."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state1 = hass.states.get("switch.epc8041_outlet_1")
    assert state1 is not None
    assert state1.state == STATE_ON

    state2 = hass.states.get("switch.epc8041_outlet_2")
    assert state2 is not None
    assert state2.state == STATE_OFF

    entry1 = entity_registry.async_get("switch.epc8041_outlet_1")
    assert entry1 is not None
    assert entry1.unique_id == "00:19:32:01:a3:3e_port_1"


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switch_turn_on_and_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning switches on and off."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        GudeClient, "set_outlet_state", new_callable=AsyncMock
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.epc8041_outlet_2"},
            blocking=True,
        )
        mock_set_state.assert_called_once_with(2, True)

    with patch.object(
        GudeClient, "set_outlet_state", new_callable=AsyncMock
    ) as mock_set_state:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.epc8041_outlet_1"},
            blocking=True,
        )
        mock_set_state.assert_called_once_with(1, False)


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when toggling switch fails."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch.object(
            GudeClient,
            "set_outlet_state",
            side_effect=GudeConnectionError("Network timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.epc8041_outlet_1"},
            blocking=True,
        )

    with (
        patch.object(
            GudeClient,
            "set_outlet_state",
            side_effect=GudeConnectionError("Network timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.epc8041_outlet_1"},
            blocking=True,
        )
