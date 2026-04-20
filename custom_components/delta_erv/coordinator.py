"""DataUpdateCoordinator for the Delta ERV integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    REG_ABNORMAL_STATUS,
    REG_BYPASS_FUNCTION,
    REG_EXHAUST_AIR_1_PCT,
    REG_EXHAUST_FAN_SPEED,
    REG_FAN_SPEED,
    REG_INDOOR_RETURN_TEMP,
    REG_INTERNAL_CIRCULATION,
    REG_OUTDOOR_TEMP,
    REG_POWER,
    REG_SUPPLY_AIR_1_PCT,
    REG_SUPPLY_FAN_SPEED,
    REG_SYSTEM_STATUS,
)
from .modbus import DeltaERVModbusClient

_LOGGER = logging.getLogger(__name__)

# Every register any entity currently reads. Polled once per cycle by
# the coordinator — previously each entity issued its own read loop.
REGISTERS_TO_POLL: tuple[int, ...] = (
    REG_POWER,
    REG_FAN_SPEED,
    REG_SUPPLY_AIR_1_PCT,
    REG_EXHAUST_AIR_1_PCT,
    REG_SUPPLY_FAN_SPEED,
    REG_EXHAUST_FAN_SPEED,
    REG_BYPASS_FUNCTION,
    REG_INTERNAL_CIRCULATION,
    REG_ABNORMAL_STATUS,
    REG_OUTDOOR_TEMP,
    REG_INDOOR_RETURN_TEMP,
    REG_SYSTEM_STATUS,
)


class DeltaERVDataCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls all Delta ERV registers in one cycle and fans out to entities."""

    def __init__(
        self, hass: HomeAssistant, client: DeltaERVModbusClient, name: str
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({name})",
            update_interval=timedelta(seconds=5),
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, int]:
        """Read every polled register. Raises UpdateFailed on any failure.

        Some registers return None on models that don't implement them
        (e.g. VEB500+ lack the temperature sensors). We tolerate per-
        register misses by leaving them out of the data dict — entities
        downstream check for presence. The coordinator only fails if the
        power register itself is unreadable, which indicates the bus is
        actually down.
        """
        data: dict[int, int] = {}
        power = await self.client.async_read_register(REG_POWER)
        if power is None:
            raise UpdateFailed(
                "Failed to read REG_POWER — device unreachable or Modbus "
                "error"
            )
        data[REG_POWER] = power.registers[0]

        for register in REGISTERS_TO_POLL:
            if register == REG_POWER:
                continue
            result = await self.client.async_read_register(register)
            if result is not None:
                data[register] = result.registers[0]
        return data
