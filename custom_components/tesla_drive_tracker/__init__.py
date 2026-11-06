"""Follow a Tesla's drives from the integrations that already talk to it."""
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import DriveConfigEntry, DriveCoordinator, async_remove_storage
from .websocket import async_setup_websocket

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

DATA_STARTED_AT: HassKey[float] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Note when source values became trustworthy, once per run of Home Assistant.

    Sources write their restored values while Home Assistant starts, so anything
    reported before it finished is treated as restored. A reload keeps this mark,
    because the values a running car has reported are still real.
    """

    @callback
    def mark(hass: HomeAssistant) -> None:
        hass.data[DATA_STARTED_AT] = dt_util.utcnow().timestamp()

    mark(hass)
    async_at_started(hass, mark)
    async_setup_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DriveConfigEntry) -> bool:
    """Start following one car."""
    coordinator = DriveCoordinator(hass, entry, lambda: hass.data[DATA_STARTED_AT])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DriveConfigEntry) -> bool:
    """Stop following one car, keeping its trip for the next load."""
    coordinator = entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator.async_close_subscribers()
        await coordinator.async_save()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: DriveConfigEntry) -> None:
    """Delete the car's trail and trip memory."""
    await async_remove_storage(hass, entry.entry_id)
    ir.async_delete_issue(hass, DOMAIN, f"no_sources_{entry.entry_id}")
