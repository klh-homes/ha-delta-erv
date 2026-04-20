#!/usr/bin/env python3
"""Mock Modbus TCP server for Delta ERV integration testing."""
import logging
import random
import time
from threading import Thread

from delta_erv_registers import (
    EXHAUST_MAX_RPM,
    EXHAUST_MIN_RPM,
    POWER_OFF,
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
    SUPPLY_MAX_RPM,
    SUPPLY_MIN_RPM,
)
from pymodbus.datastore import (
    ModbusDeviceContext,
    ModbusSequentialDataBlock,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
_LOGGER = logging.getLogger(__name__)


class DeltaERVMockServer:
    """Mock Modbus server that simulates a Delta ERV well enough for tests.

    The simulation is intentionally modest — just enough so a live pytest
    against this server produces plausible, deterministic-ish values for
    entity read paths. Tests that need exact values should set registers
    directly via `server.context.setValues` with `simulate=False`.
    """

    DEFAULT_DEVICE_ID = 100

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5020,
        simulate: bool = True,
    ):
        self.host = host
        self.port = port
        self.simulate = simulate
        self.server = None
        self.running = False
        self._initialize_datastore()

    def _initialize_datastore(self):
        # 0x7000 entries is overkill for the ERV's 0x00-0x18 range but keeps
        # parity with the medole mock and leaves room for future additions.
        block = ModbusSequentialDataBlock(0, [0] * 0x7000)
        self.context = ModbusDeviceContext(hr=block)
        self.server_context = ModbusServerContext(
            devices={self.DEFAULT_DEVICE_ID: self.context}, single=False
        )

    def set_initial_values(self):
        # Power off by default — matches a Delta ERV cold-boot state.
        self.context.setValues(3, REG_POWER, [POWER_OFF])
        self.context.setValues(3, REG_FAN_SPEED, [0])
        self.context.setValues(3, REG_SUPPLY_AIR_1_PCT, [0])
        self.context.setValues(3, REG_EXHAUST_AIR_1_PCT, [0])
        self.context.setValues(3, REG_SUPPLY_FAN_SPEED, [0])
        self.context.setValues(3, REG_EXHAUST_FAN_SPEED, [0])
        self.context.setValues(3, REG_BYPASS_FUNCTION, [0])
        self.context.setValues(3, REG_INTERNAL_CIRCULATION, [0])
        self.context.setValues(3, REG_ABNORMAL_STATUS, [0])
        self.context.setValues(3, REG_SYSTEM_STATUS, [0])
        # 25°C outside, 24°C indoor return — reasonable defaults.
        self.context.setValues(3, REG_OUTDOOR_TEMP, [25])
        self.context.setValues(3, REG_INDOOR_RETURN_TEMP, [24])

    def _simulate_once(self):
        """One tick of the simulation loop.

        Derives measured fan speeds from the register percentages and
        nudges temperatures a little. Kept small and side-effect-only.
        """
        power = self.context.getValues(3, REG_POWER, 1)[0]
        supply_pct = self.context.getValues(3, REG_SUPPLY_AIR_1_PCT, 1)[0]
        exhaust_pct = self.context.getValues(3, REG_EXHAUST_AIR_1_PCT, 1)[0]

        if power and supply_pct:
            supply_rpm = int(
                SUPPLY_MIN_RPM
                + (SUPPLY_MAX_RPM - SUPPLY_MIN_RPM) * min(supply_pct, 60) / 60
            )
        else:
            supply_rpm = 0

        if power and exhaust_pct:
            exhaust_rpm = int(
                EXHAUST_MIN_RPM
                + (EXHAUST_MAX_RPM - EXHAUST_MIN_RPM)
                * min(exhaust_pct, 50)
                / 50
            )
        else:
            exhaust_rpm = 0

        self.context.setValues(3, REG_SUPPLY_FAN_SPEED, [supply_rpm])
        self.context.setValues(3, REG_EXHAUST_FAN_SPEED, [exhaust_rpm])

        # Gentle temperature wobble.
        outdoor = self.context.getValues(3, REG_OUTDOOR_TEMP, 1)[0]
        indoor = self.context.getValues(3, REG_INDOOR_RETURN_TEMP, 1)[0]
        self.context.setValues(
            3, REG_OUTDOOR_TEMP, [int(outdoor + random.uniform(-0.5, 0.5))]
        )
        self.context.setValues(
            3, REG_INDOOR_RETURN_TEMP, [int(indoor + random.uniform(-0.3, 0.3))]
        )

        # System status bit0 = running.
        self.context.setValues(3, REG_SYSTEM_STATUS, [1 if power else 0])

    def _simulation_loop(self):
        self.set_initial_values()
        while self.running:
            self._simulate_once()
            time.sleep(5)

    async def start(self):
        if self.running:
            _LOGGER.warning("Server already running")
            return
        self.running = True

        if self.simulate:
            thread = Thread(target=self._simulation_loop, daemon=True)
            thread.start()
        else:
            self.set_initial_values()

        _LOGGER.info(
            "Starting Delta ERV mock Modbus server on %s:%s",
            self.host,
            self.port,
        )
        self.server = await StartAsyncTcpServer(
            context=self.server_context, address=(self.host, self.port)
        )

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.server:
            self.server.server_close()
            _LOGGER.info("Delta ERV mock Modbus server stopped")


if __name__ == "__main__":
    import asyncio

    server = DeltaERVMockServer()

    async def main():
        try:
            await server.start()
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            _LOGGER.info("Server stopped by user")
        finally:
            server.stop()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
