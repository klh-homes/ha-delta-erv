"""Shared pytest fixtures for ha-delta-erv tests."""
import asyncio
import socket
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "mock-server"))


def _stub_homeassistant_if_missing():
    """Provide a minimal homeassistant.core stub so modbus.py can import.

    modbus.py only uses HomeAssistant as a type hint, so a bare class is
    enough. If the real homeassistant package is installed (for entity
    tests), this no-ops.
    """
    try:
        import homeassistant.core  # noqa: F401

        return
    except ImportError:
        pass

    ha = ModuleType("homeassistant")
    ha_core = ModuleType("homeassistant.core")
    ha_core.HomeAssistant = type("HomeAssistant", (), {})
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.core"] = ha_core


_stub_homeassistant_if_missing()

from mock_modbus_server import DeltaERVMockServer  # noqa: E402


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


async def _wait_until_listening(
    host: str, port: int, timeout: float = 3.0
) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.05)
    raise RuntimeError(
        f"Port {host}:{port} did not become listening within {timeout}s"
    )


@pytest.fixture
async def mock_server():
    """Start a Delta ERV mock Modbus server on a free port, simulation off."""
    port = _find_free_port()
    server = DeltaERVMockServer(
        host="localhost", port=port, simulate=False
    )
    task = asyncio.create_task(server.start())

    try:
        await _wait_until_listening("localhost", port)
    except Exception:
        task.cancel()
        raise

    try:
        yield server
    finally:
        server.stop()
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass


@pytest.fixture
def fake_hass():
    """Minimal HomeAssistant-like object exposing async_add_executor_job."""

    class FakeHass:
        async def async_add_executor_job(self, func, *args):
            return await asyncio.to_thread(func, *args)

    return FakeHass()


@pytest.fixture
def fake_client():
    """A stand-in DeltaERVModbusClient that returns canned register values.

    Tests seed `client.values[register] = int_value` and drive entities
    or a coordinator. Writes are recorded in `client.writes` as
    (address, value) tuples.
    """

    class FakeClient:
        def __init__(self):
            self.values: dict[int, int] = {}
            self.writes: list[tuple[int, int]] = []
            self.multi_writes: list[tuple[int, list[int]]] = []

        async def async_read_register(self, address: int, count: int = 1):
            if address not in self.values:
                return None
            result = MagicMock()
            result.registers = [self.values[address]]
            result.isError = MagicMock(return_value=False)
            return result

        async def async_write_register(self, address: int, value: int) -> bool:
            self.writes.append((address, value))
            self.values[address] = value
            return True

        async def async_write_registers(
            self, address: int, values: list[int]
        ) -> bool:
            self.multi_writes.append((address, values))
            for i, v in enumerate(values):
                self.values[address + i] = v
            return True

    return FakeClient()
