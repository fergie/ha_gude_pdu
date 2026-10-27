"""Sensor platform for GUDE PDU devices."""  # codespell:ignore gude

from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .api import GudeSensorValue
from .coordinator import GudeConfigEntry, GudeDataUpdateCoordinator
from .entity import GudeEntity


@dataclass(frozen=True, kw_only=True)
class GudeSensorEntityDescription(SensorEntityDescription):
    """Describes a PDU sensor entity."""

    sensor_id: str


_UNIT_SENSOR_MAP: dict[
    str,
    tuple[SensorDeviceClass | None, str | None, SensorStateClass],
] = {
    "deg C": (
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    "°C": (
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    "C": (
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    "%": (
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        SensorStateClass.MEASUREMENT,
    ),
    "hPa": (
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        UnitOfPressure.HPA,
        SensorStateClass.MEASUREMENT,
    ),
    "V": (
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    "A": (
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
        SensorStateClass.MEASUREMENT,
    ),
    "W": (
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        SensorStateClass.MEASUREMENT,
    ),
    "VA": (
        SensorDeviceClass.APPARENT_POWER,
        UnitOfApparentPower.VOLT_AMPERE,
        SensorStateClass.MEASUREMENT,
    ),
    "VAR": (
        SensorDeviceClass.REACTIVE_POWER,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        SensorStateClass.MEASUREMENT,
    ),
    "Hz": (
        SensorDeviceClass.FREQUENCY,
        UnitOfFrequency.HERTZ,
        SensorStateClass.MEASUREMENT,
    ),
    "kWh": (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kVARh": (
        None,
        "kVARh",
        SensorStateClass.TOTAL_INCREASING,
    ),
}

_NAME_SUBSTRING_SENSOR_MAP: tuple[
    tuple[str, SensorDeviceClass | None, str | None, SensorStateClass], ...
] = (
    (
        "temp",
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "humid",
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "pressure",
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        UnitOfPressure.HPA,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "volt",
        SensorDeviceClass.VOLTAGE,
        UnitOfElectricPotential.VOLT,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "current",
        SensorDeviceClass.CURRENT,
        UnitOfElectricCurrent.AMPERE,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "activepower",
        SensorDeviceClass.POWER,
        UnitOfPower.WATT,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "apparentpower",
        SensorDeviceClass.APPARENT_POWER,
        UnitOfApparentPower.VOLT_AMPERE,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "reactivepower",
        SensorDeviceClass.REACTIVE_POWER,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "frequency",
        SensorDeviceClass.FREQUENCY,
        UnitOfFrequency.HERTZ,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "energy",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    (
        "powerfactor",
        SensorDeviceClass.POWER_FACTOR,
        None,
        SensorStateClass.MEASUREMENT,
    ),
)


def _match_sensor_classification(
    unit: str, name_lower: str
) -> tuple[SensorDeviceClass | None, str | None, SensorStateClass] | None:
    """Match a sensor's unit or field name to device class, unit, and state class."""
    if unit in _UNIT_SENSOR_MAP:
        return _UNIT_SENSOR_MAP[unit]
    if name_lower == "power":
        return (
            SensorDeviceClass.POWER,
            UnitOfPower.WATT,
            SensorStateClass.MEASUREMENT,
        )
    for substr, dev_class, native_unit, state_class in _NAME_SUBSTRING_SENSOR_MAP:
        if substr in name_lower:
            return (dev_class, native_unit, state_class)
    return None


def _determine_sensor_description(sensor: GudeSensorValue) -> SensorEntityDescription:
    """Determine entity description from sensor metadata."""
    unit = (sensor.unit or "").strip()
    name_lower = sensor.field_name.lower()
    is_diagnostic = sensor.sensor_type == 20 or name_lower in (
        "tcpu",
        "vsystem",
        "vaux",
        "vmain",
        "fan",
        "alert",
    )
    category = EntityCategory.DIAGNOSTIC if is_diagnostic else None
    enabled_default = name_lower not in (
        "vsystem",
        "vaux",
        "vmain",
        "apparentpower",
        "reactivepower",
    ) and unit not in ("VA", "VAR", "kVARh")

    matched = _match_sensor_classification(unit, name_lower)
    if matched is not None:
        device_class, native_unit, state_class = matched
        return SensorEntityDescription(
            key=sensor.sensor_id,
            device_class=device_class,
            native_unit_of_measurement=native_unit,
            state_class=state_class,
            entity_category=category,
            entity_registry_enabled_default=enabled_default,
        )

    fallback_state_class = (
        SensorStateClass.MEASUREMENT if isinstance(sensor.value, (int, float)) else None
    )
    return SensorEntityDescription(
        key=sensor.sensor_id,
        native_unit_of_measurement=sensor.unit or None,
        state_class=fallback_state_class,
        entity_category=category,
        entity_registry_enabled_default=enabled_default,
    )


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GudeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PDU sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []

    # Dynamic sensors from status data
    for sensor_id, sensor_val in coordinator.data.sensors.items():
        description = _determine_sensor_description(sensor_val)
        entities.append(GudeSensor(coordinator, entry, sensor_id, description))

    # Uptime diagnostic sensor
    entities.append(GudeUptimeSensor(coordinator, entry))

    async_add_entities(entities)


class GudeSensor(GudeEntity, SensorEntity):
    """Sensor entity for a PDU metric."""

    def __init__(
        self,
        coordinator: GudeDataUpdateCoordinator,
        entry: GudeConfigEntry,
        sensor_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor entity."""
        super().__init__(coordinator, entry)
        self.sensor_id = sensor_id
        self.entity_description = description
        formatted_mac = dr.format_mac(coordinator.data.device_info.mac)
        self._attr_unique_id = f"{formatted_mac}_{sensor_id}"
        self._attr_name = coordinator.data.sensors[sensor_id].name

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        sensor = self.coordinator.data.sensors.get(self.sensor_id)
        if sensor is None or sensor.value is None:
            return None
        if isinstance(sensor.value, float) and sensor.precision is not None:
            return round(sensor.value, sensor.precision)
        return sensor.value


class GudeUptimeSensor(GudeEntity, SensorEntity):
    """Diagnostic sensor for PDU uptime."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "uptime"

    def __init__(
        self,
        coordinator: GudeDataUpdateCoordinator,
        entry: GudeConfigEntry,
    ) -> None:
        """Initialise the uptime sensor."""
        super().__init__(coordinator, entry)
        formatted_mac = dr.format_mac(coordinator.data.device_info.mac)
        self._attr_unique_id = f"{formatted_mac}_uptime"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the device uptime in seconds."""
        misc = self.coordinator.data.raw_data.get("misc")
        if isinstance(misc, dict):
            val = misc.get("uptime")
            if isinstance(val, (int, float)):
                return int(val)
        return None
