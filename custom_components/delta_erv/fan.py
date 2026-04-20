"""Fan platform for Delta ERV integration."""

import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    EXHAUST_MAX_REGISTER_PCT,
    EXHAUST_MIN_REGISTER_PCT,
    FAN_SPEED_CUSTOM_1,
    POWER_OFF,
    POWER_ON,
    REG_EXHAUST_AIR_1_PCT,
    REG_FAN_SPEED,
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    SUPPLY_MAX_REGISTER_PCT,
    SUPPLY_MIN_REGISTER_PCT,
)
from .coordinator import DeltaERVDataCoordinator

_LOGGER = logging.getLogger(__name__)


def calculate_fan_percentages(user_percentage: int) -> tuple[int, int]:
    """Map user's 0-100% to (supply_pct, exhaust_pct) register values.

    The device has non-linear register mapping:
    - 0% register = fan off
    - 1% register = min RPM (400 / 380)
    - 48% / 62% register = max RPM (1840 / 2300)

    User 0-100% is quantized to 10% steps for consistency with speed_count.
    """
    if user_percentage == 0:
        return 0, 0

    quantized_pct = round(user_percentage / 10) * 10
    quantized_pct = max(0, min(100, quantized_pct))

    exhaust_pct = int(
        EXHAUST_MIN_REGISTER_PCT
        + (quantized_pct - 10)
        / 90.0
        * (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
    )
    supply_pct = int(
        SUPPLY_MIN_REGISTER_PCT
        + (quantized_pct - 10)
        / 90.0
        * (SUPPLY_MAX_REGISTER_PCT - SUPPLY_MIN_REGISTER_PCT)
    )

    exhaust_pct = max(
        EXHAUST_MIN_REGISTER_PCT, min(EXHAUST_MAX_REGISTER_PCT, exhaust_pct)
    )
    supply_pct = max(
        SUPPLY_MIN_REGISTER_PCT, min(SUPPLY_MAX_REGISTER_PCT, supply_pct)
    )

    _LOGGER.debug(
        f"User {user_percentage}% (quantized: {quantized_pct}%) -> "
        f"Exhaust register: {exhaust_pct}%, Supply register: {supply_pct}%"
    )

    return supply_pct, exhaust_pct


def calculate_user_percentage(supply_pct: int, exhaust_pct: int) -> int:
    """Reverse the mapping from the exhaust register to user percentage."""
    if exhaust_pct == 0:
        return 0

    user_pct = int(
        10
        + (exhaust_pct - EXHAUST_MIN_REGISTER_PCT)
        / (EXHAUST_MAX_REGISTER_PCT - EXHAUST_MIN_REGISTER_PCT)
        * 90
    )
    quantized = round(user_pct / 10) * 10
    return max(0, min(100, quantized))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV fan platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    async_add_entities([DeltaERVFan(coordinator, name)])


class DeltaERVFan(CoordinatorEntity[DeltaERVDataCoordinator], FanEntity):
    """Representation of a Delta ERV fan device."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 10  # 10% steps

    def __init__(self, coordinator: DeltaERVDataCoordinator, name: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}_fan"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._attr_unique_id)},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }

    @property
    def _client(self):
        """Modbus client used for writes — reads go through the coordinator."""
        return self.coordinator.client

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return data.get(REG_POWER) == POWER_ON

    @property
    def percentage(self) -> Optional[int]:
        data = self.coordinator.data or {}
        if data.get(REG_POWER) != POWER_ON:
            return 0

        supply_pct = data.get(REG_SUPPLY_AIR_1_PCT)
        exhaust_pct = data.get(REG_EXHAUST_AIR_1_PCT)
        if supply_pct is None or exhaust_pct is None:
            return None
        return calculate_user_percentage(supply_pct, exhaust_pct)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return

        percentage = max(0, min(100, percentage))
        supply_pct, exhaust_pct = calculate_fan_percentages(percentage)

        ok_supply = await self._client.async_write_register(
            REG_SUPPLY_AIR_1_PCT, supply_pct
        )
        ok_exhaust = await self._client.async_write_register(
            REG_EXHAUST_AIR_1_PCT, exhaust_pct
        )

        if ok_supply and ok_exhaust:
            ok_speed = await self._client.async_write_register(
                REG_FAN_SPEED, FAN_SPEED_CUSTOM_1
            )
            if ok_speed:
                _LOGGER.debug(f"Set fan speed to {percentage}%")
                if not self.is_on:
                    await self._client.async_write_register(REG_POWER, POWER_ON)
            else:
                _LOGGER.error("Failed to set fan speed register to Custom 1")
        else:
            _LOGGER.error(f"Failed to set fan percentage to {percentage}%")

        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, restoring a previous speed if known."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return

        current_pct = self.percentage
        if current_pct is None or current_pct == 0:
            await self.async_set_percentage(30)  # default low speed
            return

        # Already on at a known speed, just make sure power is on.
        if not await self._client.async_write_register(REG_POWER, POWER_ON):
            _LOGGER.error("Failed to turn on ERV fan")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if not await self._client.async_write_register(REG_POWER, POWER_OFF):
            _LOGGER.error("Failed to turn off ERV fan")
        await self.coordinator.async_request_refresh()
