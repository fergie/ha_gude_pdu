"""Test GUDE PDU switch platform."""  # codespell:ignore gude

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gude_pdu.api import GudeClient, GudeConnectionError
from custom_components.gude_pdu.const import CONF_USE_OUTLET_NAMES, DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_CONFIG_ENTRY_DATA, MOCK_MAC


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switches keep consistent entity IDs while devices use API names."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state1 = hass.states.get("switch.epc8041_outlet_1")
    assert state1 is not None
    assert state1.state == STATE_ON
    assert state1.attributes.get("friendly_name") == "1: Power Port 1"

    state2 = hass.states.get("switch.epc8041_outlet_2")
    assert state2 is not None
    assert state2.state == STATE_OFF
    assert state2.attributes.get("friendly_name") == "2: Power Port 2"

    entry1 = entity_registry.async_get("switch.epc8041_outlet_1")
    assert entry1 is not None
    assert entry1.unique_id == "00:19:32:01:a3:3e_port_1"

    parent_device = device_registry.async_get_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert parent_device is not None

    child_devices = dr.async_entries_for_parent_device(
        device_registry, parent_device.id
    )
    assert len(child_devices) == 4

    child_device1 = device_registry.async_get_child_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e_port_1"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert child_device1 is not None
    assert entry1.device_id == child_device1.id
    assert child_device1.parent_device_id == parent_device.id
    assert child_device1.identifiers == {(DOMAIN, "00:19:32:01:a3:3e_port_1")}
    assert child_device1.name == "1: Power Port 1"


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switches_numbered_outlet_names(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test outlet child devices use localised numbered names when configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_ENTRY_DATA, CONF_USE_OUTLET_NAMES: False},
        unique_id=MOCK_MAC,
        title="epc8041",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state1 = hass.states.get("switch.epc8041_outlet_1")
    assert state1 is not None
    assert state1.state == STATE_ON
    assert state1.attributes.get("friendly_name") == "Outlet 1"

    child_device1 = device_registry.async_get_child_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e_port_1"),
        config_entry_id=entry.entry_id,
    )
    assert child_device1 is not None
    assert child_device1.name == "Outlet 1"


async def test_switches_dynamic_outlet_name_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8041_fixture: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test child device name updates on coordinator poll when renamed in GUDE UI."""
    with patch.object(GudeClient, "_request", return_value=epc8041_fixture):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    child_device1 = device_registry.async_get_child_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e_port_1"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert child_device1 is not None
    assert child_device1.name == "1: Power Port 1"

    renamed_fixture = {
        **epc8041_fixture,
        "outputs": [
            {"name": "24-port switch", "state": 1, "type": 1},
            {"name": "", "state": 0, "type": 1},
            *epc8041_fixture["outputs"][2:],
            {"name": "Unregistered Port 5", "state": 0, "type": 1},
        ],
    }
    coordinator = mock_config_entry.runtime_data.coordinator
    with patch.object(GudeClient, "_request", return_value=renamed_fixture):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    child_device1 = device_registry.async_get_child_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e_port_1"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert child_device1 is not None
    assert child_device1.name == "1: 24-port switch"

    state1 = hass.states.get("switch.epc8041_outlet_1")
    assert state1 is not None
    assert state1.attributes.get("friendly_name") == "1: 24-port switch"

    # Empty name in API falls back to localised "Outlet 2"
    child_device2 = device_registry.async_get_child_device_by_identifier(
        identifier=(DOMAIN, "00:19:32:01:a3:3e_port_2"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert child_device2 is not None
    assert child_device2.name == "Outlet 2"


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


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_switch_missing_outlet_on_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8041_fixture: dict[str, Any],
) -> None:
    """Test switch state is unknown if the outlet disappears from status outputs."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    no_outputs_fixture = {**epc8041_fixture, "outputs": []}
    with patch.object(GudeClient, "_request", return_value=no_outputs_fixture):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.epc8041_outlet_1")
    assert state1 is not None
    assert state1.state == STATE_UNKNOWN
