"""Test GUDE PDU sensor platform."""  # codespell:ignore gude

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.gude_pdu.api import GudeClient, GudeSensorValue
from custom_components.gude_pdu.const import DOMAIN
from custom_components.gude_pdu.sensor import (
    _determine_sensor_description,
    _get_sensor_port_index,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
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

    # Voltage sensor
    voltage = hass.states.get("sensor.epc8041_l1_voltage")
    assert voltage is not None
    assert voltage.state == "240.62"
    assert voltage.attributes.get("unit_of_measurement") == "V"
    assert voltage.attributes.get("device_class") == "voltage"

    # Current sensor
    current = hass.states.get("sensor.epc8041_l1_current")
    assert current is not None
    assert current.state == "1.25"
    assert current.attributes.get("unit_of_measurement") == "A"
    assert current.attributes.get("device_class") == "current"

    # Active power sensor
    power = hass.states.get("sensor.epc8041_l1_activepower")
    assert power is not None
    assert power.state == "300.0"
    assert power.attributes.get("unit_of_measurement") == "W"
    assert power.attributes.get("device_class") == "power"

    # Energy sensor
    energy = hass.states.get("sensor.epc8041_l1_absactenergyres")
    assert energy is not None
    assert energy.state == "45.123"
    assert energy.attributes.get("unit_of_measurement") == "kWh"
    assert energy.attributes.get("device_class") == "energy"

    # CPU Temperature diagnostic sensor
    tcpu = hass.states.get("sensor.epc8041_system_i1_tcpu")
    assert tcpu is not None
    assert tcpu.state == "42.5"
    assert tcpu.attributes.get("unit_of_measurement") == "°C"
    assert tcpu.attributes.get("device_class") == "temperature"

    # Uptime diagnostic sensor
    uptime = hass.states.get("sensor.epc8041_uptime")
    assert uptime is not None
    assert uptime.state == "23625"
    assert uptime.attributes.get("unit_of_measurement") == "s"
    assert uptime.attributes.get("device_class") == "duration"

    # Check entity registry unique_id
    entry = entity_registry.async_get("sensor.epc8041_l1_voltage")
    assert entry is not None
    assert entry.unique_id == "00:19:32:01:a3:3e_9_l1_voltage"

    # Secondary / internal sensors disabled by default
    for entity_id in (
        "sensor.epc8041_system_i1_vsystem",
        "sensor.epc8041_l1_apparentpower",
        "sensor.epc8041_l1_reactivepower",
    ):
        disabled_entry = entity_registry.async_get(entity_id)
        assert disabled_entry is not None
        assert disabled_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
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

    hum = hass.states.get("sensor.epc8291_1_humidity")
    assert hum is not None
    assert hum.state == "45.0"
    assert hum.attributes.get("unit_of_measurement") == "%"
    assert hum.attributes.get("device_class") == "humidity"

    press = hass.states.get("sensor.epc8291_1_pressure")
    assert press is not None
    assert press.state == "1013.2"
    assert press.attributes.get("unit_of_measurement") == "hPa"
    assert press.attributes.get("device_class") == "atmospheric_pressure"


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

    entry = entity_registry.async_get("sensor.epc8041_outlet_1_activepower")
    assert entry is not None
    assert entry.device_id is not None
    child_device = device_registry.async_get(entry.device_id)
    assert isinstance(child_device, dr.ChildDeviceEntry)
    assert child_device.identifiers == {(DOMAIN, "00:19:32:01:a3:3e_port_1")}


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
