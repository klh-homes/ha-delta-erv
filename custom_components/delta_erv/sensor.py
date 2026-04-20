"""Sensor platform for Delta ERV integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    REG_ABNORMAL_STATUS,
    REG_EXHAUST_FAN_SPEED,
    REG_INDOOR_RETURN_TEMP,
    REG_OUTDOOR_TEMP,
    REG_SUPPLY_FAN_SPEED,
    REG_SYSTEM_STATUS,
    STATUS_EEPROM_ERROR,
    STATUS_EXHAUST_FAN_ERROR,
    STATUS_INDOOR_TEMP_ERROR,
    STATUS_OUTDOOR_TEMP_ERROR,
    STATUS_SUPPLY_FAN_ERROR,
)
from .coordinator import DeltaERVDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    sensors = [
        DeltaERVTemperatureSensor(
            coordinator,
            name,
            "outdoor_temp",
            "Outdoor Temperature",
            REG_OUTDOOR_TEMP,
        ),
        DeltaERVTemperatureSensor(
            coordinator,
            name,
            "indoor_temp",
            "Indoor Return Temperature",
            REG_INDOOR_RETURN_TEMP,
        ),
        DeltaERVSpeedSensor(
            coordinator,
            name,
            "supply_fan_speed",
            "Supply Fan Speed",
            REG_SUPPLY_FAN_SPEED,
        ),
        DeltaERVSpeedSensor(
            coordinator,
            name,
            "exhaust_fan_speed",
            "Exhaust Fan Speed",
            REG_EXHAUST_FAN_SPEED,
        ),
        DeltaERVAbnormalStatusSensor(coordinator, name),
        DeltaERVSystemStatusSensor(coordinator, name),
    ]
    async_add_entities(sensors)


class DeltaERVBaseSensor(
    CoordinatorEntity[DeltaERVDataCoordinator], SensorEntity
):
    """Base class for Delta ERV sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DeltaERVDataCoordinator,
        device_name: str,
        sensor_id: str,
        sensor_name: str,
        register: int,
    ) -> None:
        super().__init__(coordinator)
        self._register = register
        self._attr_unique_id = f"{device_name}_{sensor_id}"
        self._attr_name = sensor_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{device_name}_fan")},
            "name": device_name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

    @property
    def available(self) -> bool:
        """Available whenever the coordinator has a value for our register."""
        return super().available and self._register in (
            self.coordinator.data or {}
        )


class DeltaERVTemperatureSensor(DeltaERVBaseSensor):
    """Temperature sensor for Delta ERV."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> float | None:
        raw = (self.coordinator.data or {}).get(self._register)
        if raw is None:
            return None
        # Delta ERV returns a signed 16-bit integer in °C.
        return float(raw - 65536 if raw > 32767 else raw)


class DeltaERVSpeedSensor(DeltaERVBaseSensor):
    """Fan speed (RPM) sensor for Delta ERV."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:fan"

    @property
    def native_value(self) -> int | None:
        return (self.coordinator.data or {}).get(self._register)


class DeltaERVAbnormalStatusSensor(DeltaERVBaseSensor):
    """Abnormal status sensor — decodes error bit flags (register 0x10)."""

    _attr_icon = "mdi:information"

    def __init__(
        self, coordinator: DeltaERVDataCoordinator, device_name: str
    ) -> None:
        super().__init__(
            coordinator,
            device_name,
            "abnormal_status",
            "Abnormal Status",
            REG_ABNORMAL_STATUS,
        )

    def _status(self) -> int | None:
        return (self.coordinator.data or {}).get(REG_ABNORMAL_STATUS)

    @property
    def native_value(self) -> str | None:
        status = self._status()
        if status is None:
            return None
        any_error = status & (
            STATUS_EEPROM_ERROR
            | STATUS_INDOOR_TEMP_ERROR
            | STATUS_OUTDOOR_TEMP_ERROR
            | STATUS_EXHAUST_FAN_ERROR
            | STATUS_SUPPLY_FAN_ERROR
        )
        return "Error" if any_error else "Normal"

    @property
    def extra_state_attributes(self) -> dict:
        status = self._status()
        if status is None:
            return {}
        return {
            "eeprom_error": bool(status & STATUS_EEPROM_ERROR),
            "indoor_temp_error": bool(status & STATUS_INDOOR_TEMP_ERROR),
            "outdoor_temp_error": bool(status & STATUS_OUTDOOR_TEMP_ERROR),
            "exhaust_fan_error": bool(status & STATUS_EXHAUST_FAN_ERROR),
            "supply_fan_error": bool(status & STATUS_SUPPLY_FAN_ERROR),
            "raw_value": f"0x{status:04X}",
        }


class DeltaERVSystemStatusSensor(DeltaERVBaseSensor):
    """System status sensor (register 0x13) — running / bypass / etc."""

    _attr_icon = "mdi:information"

    def __init__(
        self, coordinator: DeltaERVDataCoordinator, device_name: str
    ) -> None:
        super().__init__(
            coordinator,
            device_name,
            "system_status",
            "System Status",
            REG_SYSTEM_STATUS,
        )

    def _status(self) -> int | None:
        return (self.coordinator.data or {}).get(REG_SYSTEM_STATUS)

    @property
    def native_value(self) -> str | None:
        status = self._status()
        if status is None:
            return None
        return "Running" if (status & 0x0001) else "Stopped"

    @property
    def extra_state_attributes(self) -> dict:
        status = self._status()
        if status is None:
            return {}
        return {
            "running": bool(status & 0x0001),
            "bypass_active": bool(status & 0x0010),
            "internal_circulation": bool(status & 0x0020),
            "low_temp_protection": bool(status & 0x0040),
            "raw_value": f"0x{status:04X}",
        }
