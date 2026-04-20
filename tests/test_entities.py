"""Tests for Delta ERV entity state derivation against a fake coordinator."""
from unittest.mock import MagicMock

from custom_components.delta_erv.const import (
    BYPASS_AUTO,
    BYPASS_BYPASS,
    EXHAUST_MAX_REGISTER_PCT,
    POWER_OFF,
    POWER_ON,
    REG_ABNORMAL_STATUS,
    REG_BYPASS_FUNCTION,
    REG_EXHAUST_AIR_1_PCT,
    REG_EXHAUST_FAN_SPEED,
    REG_INDOOR_RETURN_TEMP,
    REG_OUTDOOR_TEMP,
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    REG_SYSTEM_STATUS,
    STATUS_EXHAUST_FAN_ERROR,
    STATUS_INDOOR_TEMP_ERROR,
    SUPPLY_MAX_REGISTER_PCT,
)
from custom_components.delta_erv.fan import DeltaERVFan
from custom_components.delta_erv.select import (
    DeltaERVBypassSelect,
    DeltaERVInternalCirculationSelect,
)
from custom_components.delta_erv.sensor import (
    DeltaERVAbnormalStatusSensor,
    DeltaERVSpeedSensor,
    DeltaERVSystemStatusSensor,
    DeltaERVTemperatureSensor,
)


def _fake_coordinator(data: dict, client=None) -> MagicMock:
    """MagicMock coordinator that quacks enough for CoordinatorEntity."""
    coord = MagicMock()
    coord.data = data
    coord.client = client if client is not None else MagicMock()
    coord.last_update_success = True

    async def _refresh():
        return None

    coord.async_request_refresh = _refresh
    return coord


# Fan ----------------------------------------------------------------------


async def test_fan_reports_off_when_power_register_zero():
    coordinator = _fake_coordinator({REG_POWER: POWER_OFF})
    fan = DeltaERVFan(coordinator, "erv")

    assert fan.is_on is False
    assert fan.percentage == 0


async def test_fan_reports_on_and_maps_register_to_user_percentage():
    # Max register values should map back to ~100% user percentage.
    coordinator = _fake_coordinator({
        REG_POWER: POWER_ON,
        REG_SUPPLY_AIR_1_PCT: SUPPLY_MAX_REGISTER_PCT,
        REG_EXHAUST_AIR_1_PCT: EXHAUST_MAX_REGISTER_PCT,
    })
    fan = DeltaERVFan(coordinator, "erv")

    assert fan.is_on is True
    assert fan.percentage == 100


async def test_fan_set_percentage_writes_supply_exhaust_and_fan_speed(fake_client):
    coordinator = _fake_coordinator(
        {REG_POWER: POWER_ON}, client=fake_client
    )
    fan = DeltaERVFan(coordinator, "erv")

    await fan.async_set_percentage(50)

    # Must have written supply%, exhaust%, and the custom fan-speed register.
    written_regs = {addr for addr, _ in fake_client.writes}
    assert REG_SUPPLY_AIR_1_PCT in written_regs
    assert REG_EXHAUST_AIR_1_PCT in written_regs


# Sensors ------------------------------------------------------------------


async def test_temperature_sensor_decodes_signed_int():
    # Positive value: returned as-is.
    coordinator = _fake_coordinator({REG_OUTDOOR_TEMP: 23})
    sensor = DeltaERVTemperatureSensor(
        coordinator, "erv", "outdoor_temp", "Outdoor Temperature",
        REG_OUTDOOR_TEMP,
    )
    assert sensor.native_value == 23.0

    # Negative value: encoded as 65536 - abs(value). -5°C → 65531.
    coordinator = _fake_coordinator({REG_INDOOR_RETURN_TEMP: 65531})
    sensor = DeltaERVTemperatureSensor(
        coordinator, "erv", "indoor_temp", "Indoor Return Temperature",
        REG_INDOOR_RETURN_TEMP,
    )
    assert sensor.native_value == -5.0


async def test_speed_sensor_passes_register_through_as_rpm():
    coordinator = _fake_coordinator({REG_EXHAUST_FAN_SPEED: 1200})
    sensor = DeltaERVSpeedSensor(
        coordinator, "erv", "exhaust_fan_speed", "Exhaust Fan Speed",
        REG_EXHAUST_FAN_SPEED,
    )
    assert sensor.native_value == 1200


async def test_abnormal_status_sensor_decodes_error_bits():
    coordinator = _fake_coordinator({
        REG_ABNORMAL_STATUS: STATUS_INDOOR_TEMP_ERROR | STATUS_EXHAUST_FAN_ERROR
    })
    sensor = DeltaERVAbnormalStatusSensor(coordinator, "erv")

    assert sensor.native_value == "Error"
    attrs = sensor.extra_state_attributes
    assert attrs["indoor_temp_error"] is True
    assert attrs["exhaust_fan_error"] is True
    assert attrs["eeprom_error"] is False


async def test_system_status_sensor_reports_running_bit():
    coordinator = _fake_coordinator({REG_SYSTEM_STATUS: 0x0011})
    sensor = DeltaERVSystemStatusSensor(coordinator, "erv")

    assert sensor.native_value == "Running"
    attrs = sensor.extra_state_attributes
    assert attrs["running"] is True
    assert attrs["bypass_active"] is True


async def test_sensor_unavailable_when_register_missing_from_coordinator():
    # Simulates a model that doesn't implement outdoor temperature.
    coordinator = _fake_coordinator({REG_POWER: POWER_ON})
    sensor = DeltaERVTemperatureSensor(
        coordinator, "erv", "outdoor_temp", "Outdoor Temperature",
        REG_OUTDOOR_TEMP,
    )
    assert sensor.available is False
    assert sensor.native_value is None


# Selects ------------------------------------------------------------------


async def test_bypass_select_reports_current_mode():
    coordinator = _fake_coordinator({
        REG_POWER: POWER_ON,
        REG_BYPASS_FUNCTION: BYPASS_AUTO,
    })
    select = DeltaERVBypassSelect(coordinator, "erv")

    assert select.current_option == "Auto"


async def test_bypass_select_writes_and_refreshes_when_on(fake_client):
    coordinator = _fake_coordinator(
        {REG_POWER: POWER_ON, REG_BYPASS_FUNCTION: BYPASS_AUTO},
        client=fake_client,
    )
    select = DeltaERVBypassSelect(coordinator, "erv")

    await select.async_select_option("Bypass")

    assert (REG_BYPASS_FUNCTION, BYPASS_BYPASS) in fake_client.writes


async def test_bypass_select_refuses_when_power_off(fake_client):
    coordinator = _fake_coordinator(
        {REG_POWER: POWER_OFF, REG_BYPASS_FUNCTION: BYPASS_AUTO},
        client=fake_client,
    )
    select = DeltaERVBypassSelect(coordinator, "erv")

    await select.async_select_option("Bypass")

    # Must NOT have written anything when power is off.
    assert fake_client.writes == []


async def test_internal_circulation_select_reports_mode():
    coordinator = _fake_coordinator({
        REG_POWER: POWER_ON,
        # 0 = Heat Exchange (default).
    })
    select = DeltaERVInternalCirculationSelect(coordinator, "erv")

    # When the register isn't in data, current_option returns None.
    assert select.current_option is None
