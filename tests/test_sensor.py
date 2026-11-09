"""Test GUDE PDU sensor platform."""  # codespell:ignore gude

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gude_pdu.api import GudeClient, GudeSensorValue
from custom_components.gude_pdu.const import DOMAIN
from custom_components.gude_pdu.sensor import (
    _determine_sensor_description,
    _format_field_name,
    _format_sensor_name,
    _get_sensor_port_index,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import DEGREE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.mark.usefixtures("mock_gude_pdu_client")
async def test_sensors_epc8041(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test electrical and diagnostic sensors from EPC 8041."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    expected_states = (
        (
            "sensor.epc8041_l1_voltage",
            "240.62",
            "V",
            "voltage",
            "epc8041 L1 Voltage [V]",
        ),
        ("sensor.epc8041_l1_current", "1.25", "A", "current", "epc8041 L1 Current [A]"),
        (
            "sensor.epc8041_l1_activepower",
            "300.0",
            "W",
            "power",
            "epc8041 L1 Active Power [W]",
        ),
        (
            "sensor.epc8041_l1_powerfactor",
            "0.99",
            None,
            "power_factor",
            "epc8041 L1 Power Factor",
        ),
        (
            "sensor.epc8041_l1_absactenergyres",
            "45.123",
            "kWh",
            "energy",
            "epc8041 L1 Active Energy (resettable) [kWh]",
        ),
        (
            "sensor.epc8041_system_i1_tcpu",
            "42.5",
            "°C",
            "temperature",
            "epc8041 System I1 Tcpu [°C]",
        ),
        ("sensor.epc8041_uptime", "23625", "s", "duration", "epc8041 Uptime"),
    )
    for entity_id, expected_state, unit, dev_class, friendly_name in expected_states:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
        assert state.attributes.get("unit_of_measurement") == unit
        assert state.attributes.get("device_class") == dev_class
        assert state.attributes.get("friendly_name") == friendly_name

    # Check entity registry unique_id and original_name
    entry = entity_registry.async_get("sensor.epc8041_l1_voltage")
    assert entry is not None
    assert entry.unique_id == "00:19:32:01:a3:3e_9_l1_voltage"
    assert entry.original_name == "L1 Voltage [V]"

    # Secondary / internal sensors disabled by default
    expected_disabled_names = {
        "sensor.epc8041_system_i1_vsystem": "System I1 Vsystem [V]",
        "sensor.epc8041_l1_apparentpower": "L1 Apparent Power [VA]",
        "sensor.epc8041_l1_reactivepower": "L1 Reactive Power [var]",
    }
    for entity_id, expected_name in expected_disabled_names.items():
        disabled_entry = entity_registry.async_get(entity_id)
        assert disabled_entry is not None
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert disabled_entry.original_name == expected_name
        assert hass.states.get(entity_id) is None


async def test_sensors_epc8291_environmental(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8291_fixture: dict[str, Any],
) -> None:
    """Test environmental sensors from EPC 8291."""
    with patch.object(GudeClient, "_request", return_value=epc8291_fixture):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    temp = hass.states.get("sensor.epc8291_1_temperature")
    assert temp is not None
    assert temp.state == "21.5"
    assert temp.attributes.get("unit_of_measurement") == "°C"
    assert temp.attributes.get("device_class") == "temperature"
    assert temp.attributes.get("friendly_name") == "epc8291 1 Temperature [°C]"

    hum = hass.states.get("sensor.epc8291_1_humidity")
    assert hum is not None
    assert hum.state == "45.0"
    assert hum.attributes.get("unit_of_measurement") == "%"
    assert hum.attributes.get("device_class") == "humidity"
    assert hum.attributes.get("friendly_name") == "epc8291 1 Humidity [%]"

    press = hass.states.get("sensor.epc8291_1_pressure")
    assert press is not None
    assert press.state == "1013.2"
    assert press.attributes.get("unit_of_measurement") == "hPa"
    assert press.attributes.get("device_class") == "atmospheric_pressure"
    assert press.attributes.get("friendly_name") == "epc8291 1 Pressure [hPa]"


@pytest.mark.parametrize(
    ("field_name", "unit", "expected"),
    [
        ("Voltage", "V", "Voltage [V]"),
        ("Current", "A", "Current [A]"),
        ("Frequency", "Hz", "Frequency [Hz]"),
        ("PhaseIU", "deg", "Phase Angle [°]"),
        ("PhaseIU", "", "Phase Angle [°]"),
        ("ActivePower", "W", "Active Power [W]"),
        ("ReactivePower", "VAR", "Reactive Power [var]"),
        ("ReactivePower", "Var", "Reactive Power [var]"),
        ("ApparentPower", "VA", "Apparent Power [VA]"),
        ("PowerFactor", "", "Power Factor"),
        ("AbsActEnergyNonRes", "kWh", "Active Energy (total) [kWh]"),
        ("AbsActEnergyRes", "kWh", "Active Energy (resettable) [kWh]"),
        ("FwdActEnergyNonRes", "kWh", "Forward Active Energy (total) [kWh]"),
        ("FwdActEnergyRes", "kWh", "Forward Active Energy (resettable) [kWh]"),
        ("RevActEnergyNonRes", "kWh", "Reverse Active Energy (total) [kWh]"),
        ("RevActEnergyRes", "kWh", "Reverse Active Energy (resettable) [kWh]"),
        ("AbsReactEnergyNonRes", "kVARh", "Reactive Energy (total) [kvarh]"),
        ("RelativeTime", "s", "Relative Time [s]"),
        ("RelativeTime", "", "Relative Time [s]"),
        ("Temperature", "deg C", "Temperature [°C]"),
        ("AlertCount", None, "AlertCount"),
    ],
)
def test_format_field_name(field_name: str, unit: str | None, expected: str) -> None:
    """Test formatting of sensor field names and units."""
    assert _format_field_name(field_name, unit) == expected


def test_format_sensor_name() -> None:
    """Test formatting of sensor names with and without outlet port prefix."""
    outlet_sensor = GudeSensorValue(
        sensor_id="8_1_absactenergynonres",
        name="1 AbsActEnergyNonRes",
        value=12.345,
        unit="kWh",
        precision=3,
        sensor_type=8,
        property_id="1",
        field_name="AbsActEnergyNonRes",
    )
    assert (
        _format_sensor_name(outlet_sensor, port_index=1)
        == "Active Energy (total) [kWh]"
    )
    assert (
        _format_sensor_name(outlet_sensor, port_index=None)
        == "1 Active Energy (total) [kWh]"
    )


def test_determine_sensor_description_fallbacks() -> None:
    """Test sensor classification fallbacks for unmapped units and names."""
    power_sensor = GudeSensorValue(
        sensor_id="1_power",
        name="Power",
        value=100,
        unit="",
        precision=0,
        sensor_type=1,
        field_name="Power",
        property_id="1",
    )
    desc_power = _determine_sensor_description(power_sensor)
    assert desc_power.device_class is SensorDeviceClass.POWER
    assert desc_power.state_class is SensorStateClass.MEASUREMENT

    phase_sensor = GudeSensorValue(
        sensor_id="8_1_phaseiu",
        name="1 PhaseIU",
        value=12.5,
        unit="",
        precision=1,
        sensor_type=8,
        field_name="PhaseIU",
        property_id="1",
    )
    desc_phase = _determine_sensor_description(phase_sensor)
    assert desc_phase.device_class is None
    assert desc_phase.native_unit_of_measurement == DEGREE
    assert desc_phase.state_class is SensorStateClass.MEASUREMENT

    reltime_sensor = GudeSensorValue(
        sensor_id="8_1_relativetime",
        name="1 RelativeTime",
        value=3600,
        unit="s",
        precision=0,
        sensor_type=8,
        field_name="RelativeTime",
        property_id="1",
    )
    desc_reltime = _determine_sensor_description(reltime_sensor)
    assert desc_reltime.device_class is SensorDeviceClass.DURATION
    assert desc_reltime.native_unit_of_measurement == UnitOfTime.SECONDS
    assert desc_reltime.state_class is SensorStateClass.TOTAL_INCREASING

    custom_sensor = GudeSensorValue(
        sensor_id="1_custom",
        name="Custom Metric",
        value=12,
        unit="rpm",
        precision=None,
        sensor_type=20,
        field_name="Fan",
        property_id="1",
    )
    desc_custom = _determine_sensor_description(custom_sensor)
    assert desc_custom.device_class is None
    assert desc_custom.native_unit_of_measurement == "rpm"
    assert desc_custom.state_class is SensorStateClass.MEASUREMENT


async def test_outlet_sensors_attached_to_child_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8041_fixture: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test per-outlet sensors (type 8) attach to the outlet child device."""
    fixture = {
        **epc8041_fixture,
        "sensor_descr": [
            *epc8041_fixture["sensor_descr"],
            {
                "type": 8,
                "num": 2,
                "fields": [{"name": "ActivePower", "unit": "W", "decPrecision": 1}],
                "properties": [
                    {"id": "1", "name": "Power Port 1"},
                    {"id": "99", "name": "Unmapped Port"},
                ],
            },
        ],
        "sensor_values": [
            *epc8041_fixture["sensor_values"],
            {
                "type": 8,
                "num": 2,
                "values": [[{"v": 42.5}], [{"v": 10.0}]],
            },
        ],
    }

    with patch.object(GudeClient, "_request", return_value=fixture):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    outlet_power = hass.states.get("sensor.epc8041_outlet_1_activepower")
    assert outlet_power is not None
    assert outlet_power.state == "42.5"
    assert (
        outlet_power.attributes.get("friendly_name")
        == "1: Power Port 1 Active Power [W]"
    )

    entry = entity_registry.async_get("sensor.epc8041_outlet_1_activepower")
    assert entry is not None
    assert entry.original_name == "Active Power [W]"
    assert entry.device_id is not None
    child_device = device_registry.async_get(entry.device_id)
    assert isinstance(child_device, dr.ChildDeviceEntry)
    assert child_device.identifiers == {(DOMAIN, "00:19:32:01:a3:3e_port_1")}
    assert child_device.name == "1: Power Port 1"


def test_get_sensor_port_index() -> None:
    """Test mapping outlet sensor metadata to port index."""
    outputs = {1: object(), 2: object()}
    outlet_sensor = GudeSensorValue(
        sensor_id="8_1_activepower",
        name="1 ActivePower",
        value=10.0,
        unit="W",
        precision=1,
        sensor_type=8,
        property_id="1",
        field_name="ActivePower",
    )
    assert _get_sensor_port_index(outlet_sensor, outputs) == 1

    non_digit_sensor = GudeSensorValue(
        sensor_id="8_p1_activepower",
        name="P1 ActivePower",
        value=10.0,
        unit="W",
        precision=1,
        sensor_type=8,
        property_id="P1",
        field_name="ActivePower",
    )
    assert _get_sensor_port_index(non_digit_sensor, outputs) is None


async def test_sensor_missing_and_unrounded_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    epc8041_fixture: dict[str, Any],
) -> None:
    """Test sensor native_value with integer/unrounded values and missing data."""
    fixture_with_int = {
        **epc8041_fixture,
        "sensor_descr": [
            *epc8041_fixture["sensor_descr"],
            {
                "type": 50,
                "fields": [{"name": "AlertCount"}],
                "properties": [{"id": "1"}],
            },
        ],
        "sensor_values": [
            *epc8041_fixture["sensor_values"],
            {
                "type": 50,
                "values": [[{"v": 3}]],
            },
        ],
    }

    with patch.object(GudeClient, "_request", return_value=fixture_with_int):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    alert_state = hass.states.get("sensor.epc8041_1_alertcount")
    assert alert_state is not None
    assert alert_state.state == "3"

    # Update coordinator with empty sensors and no misc uptime
    coordinator = mock_config_entry.runtime_data.coordinator
    empty_fixture = {
        "ethernet": epc8041_fixture["ethernet"],
        "misc": {"product_name": "Expert Power Control 8041-1"},
        "outputs": [],
        "sensor_descr": [],
        "sensor_values": [],
    }
    with patch.object(GudeClient, "_request", return_value=empty_fixture):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    alert_state = hass.states.get("sensor.epc8041_1_alertcount")
    assert alert_state is not None
    assert alert_state.state == "unknown"

    uptime_state = hass.states.get("sensor.epc8041_uptime")
    assert uptime_state is not None
    assert uptime_state.state == "unknown"
