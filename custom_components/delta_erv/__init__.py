"""The Delta ERV integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_NAME, CONF_SLAVE_ID, DOMAIN
from .coordinator import DeltaERVDataCoordinator
from .modbus import DeltaERVModbusClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.SENSOR, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Delta ERV from a config entry."""
    config = entry.data
    slave_id = config[CONF_SLAVE_ID]

    client = DeltaERVModbusClient(hass, config, slave_id)
    coordinator = DeltaERVDataCoordinator(hass, client, name=config[CONF_NAME])

    # Populate initial data before platforms fetch entity state.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "config": config,
        "slave_id": slave_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if "client" in data:
            data["client"].close()

    return unload_ok
