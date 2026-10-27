"""Test GUDE PDU sensor platform."""  # codespell:ignore gude

from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gude_pdu.api import GudeClient, GudeSensorValue
from custom_components.gude_pdu.sensor import _determine_sensor_description
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


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
