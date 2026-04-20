"""Tests for DeltaERVDataCoordinator._async_update_data."""
import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.delta_erv.const import (
    REG_OUTDOOR_TEMP,
    REG_POWER,
    REG_SYSTEM_STATUS,
)
from custom_components.delta_erv.coordinator import (
    REGISTERS_TO_POLL,
    DeltaERVDataCoordinator,
)


class _CapturingCoordinator(DeltaERVDataCoordinator):
    """Bypasses DataUpdateCoordinator.__init__ so we can unit-test the poll.

    The real __init__ wants a fully-wired HomeAssistant (event loop, bus, …).
    For this unit test we only need self.client.
    """

    def __init__(self, client):
        self.client = client


async def test_coordinator_reads_every_polled_register(fake_client):
    # Seed every register the coordinator is expected to read.
    for i, reg in enumerate(REGISTERS_TO_POLL):
        fake_client.values[reg] = i + 1

    coordinator = _CapturingCoordinator(fake_client)
    data = await coordinator._async_update_data()

    assert set(data.keys()) == set(REGISTERS_TO_POLL)
    assert data[REG_POWER] == REGISTERS_TO_POLL.index(REG_POWER) + 1
    assert data[REG_OUTDOOR_TEMP] == REGISTERS_TO_POLL.index(REG_OUTDOOR_TEMP) + 1


async def test_coordinator_raises_update_failed_when_power_unreadable(fake_client):
    # fake_client.values is empty → async_read_register returns None for
    # every register, including REG_POWER, which is the trip wire.
    coordinator = _CapturingCoordinator(fake_client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_tolerates_missing_optional_registers(fake_client):
    """Some ERV models lack e.g. system-status or temperature registers.

    Missing registers should be omitted from the returned dict, NOT cause
    the whole poll to fail. Power is the only mandatory register.
    """
    fake_client.values[REG_POWER] = 1
    fake_client.values[REG_OUTDOOR_TEMP] = 25
    # Deliberately leave REG_SYSTEM_STATUS unset.

    coordinator = _CapturingCoordinator(fake_client)
    data = await coordinator._async_update_data()

    assert REG_POWER in data
    assert REG_OUTDOOR_TEMP in data
    assert REG_SYSTEM_STATUS not in data
