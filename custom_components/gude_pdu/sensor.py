"""Sensor platform for GUDE PDU devices."""  # codespell:ignore gude

from collections.abc import Mapping
from dataclasses import dataclass
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactiveEnergy,
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
    "Var": (
        SensorDeviceClass.REACTIVE_POWER,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        SensorStateClass.MEASUREMENT,
    ),
    "VAr": (
        SensorDeviceClass.REACTIVE_POWER,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        SensorStateClass.MEASUREMENT,
    ),
    "var": (
        SensorDeviceClass.REACTIVE_POWER,
        UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        SensorStateClass.MEASUREMENT,
    ),
    "Hz": (
        SensorDeviceClass.FREQUENCY,
        UnitOfFrequency.HERTZ,
        SensorStateClass.MEASUREMENT,
    ),
    "deg": (
        None,
        DEGREE,
        SensorStateClass.MEASUREMENT,
    ),
    "°": (
        None,
        DEGREE,
        SensorStateClass.MEASUREMENT,
    ),
    "s": (
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kWh": (
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kVARh": (
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kVarh": (
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kVArh": (
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorStateClass.TOTAL_INCREASING,
    ),
    "kvarh": (
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
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
        "phaseiu",
        None,
        DEGREE,
        SensorStateClass.MEASUREMENT,
    ),
    (
        "relativetime",
        SensorDeviceClass.DURATION,
        UnitOfTime.SECONDS,
        SensorStateClass.TOTAL_INCREASING,
    ),
    (
        "reactenergy",
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorStateClass.TOTAL_INCREASING,
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

_FIELD_NAME_MAP: dict[str, str] = {
    "voltage": "Voltage",
    "current": "Current",
    "frequency": "Frequency",
    "phaseiu": "Phase Angle",
    "activepower": "Active Power",
    "reactivepower": "Reactive Power",
    "apparentpower": "Apparent Power",
    "powerfactor": "Power Factor",
    "absactenergynonres": "Active Energy (total)",
    "absactenergyres": "Active Energy (resettable)",
    "fwdactenergynonres": "Forward Active Energy (total)",
    "fwdactenergyres": "Forward Active Energy (resettable)",
    "revactenergynonres": "Reverse Active Energy (total)",
    "revactenergyres": "Reverse Active Energy (resettable)",
    "absreactenergynonres": "Reactive Energy (total)",
    "absreactenergyres": "Reactive Energy (resettable)",
    "fwdreactenergynonres": "Forward Reactive Energy (total)",
    "fwdreactenergyres": "Forward Reactive Energy (resettable)",
    "revreactenergynonres": "Reverse Reactive Energy (total)",
    "revreactenergyres": "Reverse Reactive Energy (resettable)",
    "relativetime": "Relative Time",
    "residualcurrent": "Residual Current",
    "residual current": "Residual Current",
}

_DISPLAY_UNIT_MAP: dict[str, str] = {
    "deg C": UnitOfTemperature.CELSIUS,
    "C": UnitOfTemperature.CELSIUS,
    "deg": DEGREE,
    "VAR": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    "Var": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    "VAr": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    "kVARh": UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
    "kVarh": UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
    "kVArh": UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
}

_DEFAULT_FIELD_UNIT_MAP: dict[str, str] = {
    "phaseiu": "°",
    "relativetime": "s",
}


def _format_field_name(field_name: str, unit: str | None) -> str:
    """Format a PDU sensor field name with descriptive label and [unit] suffix."""
    name_lower = field_name.lower()
    label = _FIELD_NAME_MAP.get(name_lower, field_name)
    raw_unit = (unit or "").strip()
    display_unit = _DISPLAY_UNIT_MAP.get(
        raw_unit, raw_unit or _DEFAULT_FIELD_UNIT_MAP.get(name_lower, "")
    )
    if display_unit:
        return f"{label} [{display_unit}]"
    return label


def _format_sensor_name(sensor: GudeSensorValue, port_index: int | None) -> str:
    """Build the human-readable sensor entity name."""
    raw_name = (
        sensor.name.removeprefix(f"{port_index} ")
        if port_index is not None
        else sensor.name
    )
    prefix = raw_name.removesuffix(sensor.field_name).rstrip()
    formatted_field = _format_field_name(sensor.field_name, sensor.unit)
    if prefix:
        return f"{prefix} {formatted_field}"
    return formatted_field


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
    ) and unit not in (
        "VA",
        "VAR",
        "Var",
        "VAr",
        "var",
        "kVARh",
        "kVarh",
        "kVArh",
        "kvarh",
    )

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


_OUTLET_SENSOR_TYPES = frozenset({8, 17})


def _get_sensor_port_index(
    sensor: GudeSensorValue, outputs: Mapping[int, object]
) -> int | None:
    """Return the 1-based outlet port index if the sensor belongs to an outlet."""
    if sensor.sensor_type not in _OUTLET_SENSOR_TYPES:
        return None
    prop_prefix = sensor.property_id.split("_", 1)[0].split(".", 1)[0]
    if prop_prefix.isdigit():
        port_idx = int(prop_prefix)
        if port_idx in outputs:
            return port_idx
    return None


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
        sensor = coordinator.data.sensors[sensor_id]
        port_index = _get_sensor_port_index(sensor, coordinator.data.outputs)
        super().__init__(coordinator, entry, port_index=port_index)
        self.sensor_id = sensor_id
        self.entity_description = description
        formatted_mac = dr.format_mac(coordinator.data.device_info.mac)
        self._attr_unique_id = f"{formatted_mac}_{sensor_id}"
        self._suggested_object_id = (
            sensor.name.removeprefix(f"{port_index} ")
            if port_index is not None
            else sensor.name
        )
        self._attr_name = _format_sensor_name(sensor, port_index)

    @property
    @override
    def suggested_object_id(self) -> str | None:
        """Return suggested object id based on the raw API sensor name."""
        return self._suggested_object_id

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
