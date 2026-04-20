"""Select platform for Delta ERV integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BYPASS_AUTO,
    BYPASS_BYPASS,
    BYPASS_HEAT_EXCHANGE,
    DOMAIN,
    INTERNAL_CIRC_HEAT_EXCHANGE,
    INTERNAL_CIRC_INTERNAL,
    POWER_ON,
    REG_BYPASS_FUNCTION,
    REG_INTERNAL_CIRCULATION,
    REG_POWER,
)
from .coordinator import DeltaERVDataCoordinator

_LOGGER = logging.getLogger(__name__)

BYPASS_MODES = {
    "Heat Exchange": BYPASS_HEAT_EXCHANGE,
    "Bypass": BYPASS_BYPASS,
    "Auto": BYPASS_AUTO,
}
BYPASS_MODES_REVERSE = {v: k for k, v in BYPASS_MODES.items()}

INTERNAL_CIRC_MODES = {
    "Heat Exchange": INTERNAL_CIRC_HEAT_EXCHANGE,
    "Internal Circulation": INTERNAL_CIRC_INTERNAL,
}
INTERNAL_CIRC_MODES_REVERSE = {v: k for k, v in INTERNAL_CIRC_MODES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Delta ERV select platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    name = data["config"][CONF_NAME]

    async_add_entities(
        [
            DeltaERVBypassSelect(coordinator, name),
            DeltaERVInternalCirculationSelect(coordinator, name),
        ]
    )


class _DeltaERVModeSelectBase(
    CoordinatorEntity[DeltaERVDataCoordinator], SelectEntity
):
    """Shared plumbing for the bypass and internal-circulation selects."""

    _attr_has_entity_name = True
    _register: int
    _mode_map: dict[str, int]
    _mode_map_reverse: dict[int, str]
    _default_option: str

    def __init__(
        self,
        coordinator: DeltaERVDataCoordinator,
        name: str,
        unique_id_suffix: str,
        entity_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{name}_{unique_id_suffix}"
        self._attr_name = entity_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{name}_fan")},
            "name": name,
            "manufacturer": "Delta",
            "model": "ERV",
        }
        self._attr_options = list(self._mode_map.keys())

    @property
    def current_option(self) -> str | None:
        raw = (self.coordinator.data or {}).get(self._register)
        if raw is None:
            return None
        return self._mode_map_reverse.get(raw, self._default_option)

    async def async_select_option(self, option: str) -> None:
        # Both modes require the ERV to be powered on per the spec.
        data = self.coordinator.data or {}
        if data.get(REG_POWER) != POWER_ON:
            _LOGGER.error("Cannot change %s when ERV is off", self._attr_name)
            return

        value = self._mode_map.get(option)
        if value is None:
            _LOGGER.error("Unknown %s option: %s", self._attr_name, option)
            return

        if await self.coordinator.client.async_write_register(
            self._register, value
        ):
            _LOGGER.info("%s changed to %s", self._attr_name, option)
        else:
            _LOGGER.error("Failed to set %s to %s", self._attr_name, option)
        await self.coordinator.async_request_refresh()


class DeltaERVBypassSelect(_DeltaERVModeSelectBase):
    """Representation of Delta ERV Bypass Mode selector."""

    _register = REG_BYPASS_FUNCTION
    _mode_map = BYPASS_MODES
    _mode_map_reverse = BYPASS_MODES_REVERSE
    _default_option = "Heat Exchange"

    def __init__(self, coordinator: DeltaERVDataCoordinator, name: str) -> None:
        super().__init__(coordinator, name, "bypass_mode", "Bypass Mode")


class DeltaERVInternalCirculationSelect(_DeltaERVModeSelectBase):
    """Representation of Delta ERV Internal Circulation Mode selector."""

    _register = REG_INTERNAL_CIRCULATION
    _mode_map = INTERNAL_CIRC_MODES
    _mode_map_reverse = INTERNAL_CIRC_MODES_REVERSE
    _default_option = "Heat Exchange"

    def __init__(self, coordinator: DeltaERVDataCoordinator, name: str) -> None:
        super().__init__(
            coordinator,
            name,
            "internal_circulation_mode",
            "Internal Circulation Mode",
        )
