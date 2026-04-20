"""Tests for DeltaERVModbusClient — live mock server + unreachable host."""
import asyncio

import pytest

from custom_components.delta_erv.const import REG_OUTDOOR_TEMP, REG_POWER
from custom_components.delta_erv.modbus import DeltaERVModbusClient


def _config_for(mock_server) -> dict:
    return {
        "connection_type": "tcp",
        "host": "localhost",
        "tcp_port": mock_server.port,
    }


def _unreachable_config() -> dict:
    return {
        "connection_type": "tcp",
        "host": "192.0.2.1",  # RFC 5737 TEST-NET-1, black-holed
        "tcp_port": 502,
    }


@pytest.fixture(autouse=True)
def _reset_singleton():
    """DeltaERVModbusClient is a singleton keyed on host/port; clear between tests."""
    DeltaERVModbusClient._instances.clear()
    yield
    DeltaERVModbusClient._instances.clear()


async def test_read_register_live(mock_server, fake_hass):
    """Reading a register returns the value set in the mock server."""
    mock_server.context.setValues(3, REG_OUTDOOR_TEMP, [23])

    client = DeltaERVModbusClient(
        fake_hass, _config_for(mock_server), slave_id=mock_server.DEFAULT_DEVICE_ID
    )
    result = await client.async_read_register(REG_OUTDOOR_TEMP)

    assert result is not None
    assert result.registers[0] == 23


async def test_write_register_live(mock_server, fake_hass):
    """Writing a register updates mock-server state so the next read sees it."""
    client = DeltaERVModbusClient(
        fake_hass, _config_for(mock_server), slave_id=mock_server.DEFAULT_DEVICE_ID
    )

    ok = await client.async_write_register(REG_POWER, 1)
    assert ok is True

    result = await client.async_read_register(REG_POWER)
    assert result is not None
    assert result.registers[0] == 1


async def test_read_register_returns_none_on_unreachable_host(fake_hass):
    """When the host is unreachable, read returns None (no exception bubble)."""
    client = DeltaERVModbusClient(fake_hass, _unreachable_config(), slave_id=100)

    result = await client.async_read_register(REG_POWER)
    assert result is None


async def test_connect_does_not_block_event_loop(fake_hass):
    """P0 regression: a slow connect must not freeze other coroutines.

    Real-world trigger: the ERV bridge drops off the network, so
    pymodbus's socket.connect() blocks for the full TCP timeout (~1-3s).
    Before the P0 fix, _ensure_connection calls client.connect()
    synchronously on the event loop thread, freezing every other
    coroutine in Home Assistant for that entire window.

    Test strategy: monkeypatch the underlying pymodbus client so
    connect() deterministically sleeps for BLOCK_SECONDS, then measure
    how long a concurrent asyncio.sleep actually slept. If the event
    loop was frozen by connect(), the sleep overshoots badly.
    """
    import time
    from unittest.mock import MagicMock

    client = DeltaERVModbusClient(fake_hass, _unreachable_config(), slave_id=100)

    BLOCK_SECONDS = 1.0

    def slow_connect():
        time.sleep(BLOCK_SECONDS)
        return False

    fake_modbus = MagicMock()
    fake_modbus.connected = False
    fake_modbus.is_socket_open.return_value = False
    fake_modbus.connect.side_effect = slow_connect
    client.client = fake_modbus

    async def measure_sleep():
        t0 = time.monotonic()
        await asyncio.sleep(0.1)
        return time.monotonic() - t0

    # Start measure first and let it reach its await asyncio.sleep(0.1),
    # THEN kick off the blocking read. Otherwise the scheduler runs the
    # read's blocking connect() before measure has even started.
    measure_task = asyncio.create_task(measure_sleep())
    await asyncio.sleep(0.01)  # yield so measure_task enters its sleep

    read_task = asyncio.create_task(client.async_read_register(0))
    _, actual_sleep_duration = await asyncio.gather(read_task, measure_task)

    # Non-blocking: the 100ms sleep completes in ~0.1s regardless of connect.
    # Blocking: connect freezes the event loop for ~1s, so the sleep
    # actually takes ~1s.
    assert actual_sleep_duration < 0.5, (
        f"Event loop was blocked during connect(): a 100ms asyncio.sleep "
        f"actually took {actual_sleep_duration:.3f}s. _ensure_connection "
        "is calling client.connect() synchronously on the event loop "
        "thread; it needs to run via async_add_executor_job."
    )
