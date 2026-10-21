"""Monster RR270-X BLE speaker integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, PLATFORMS
from .coordinator import MonsterSpeakerCoordinator

type MonsterSpeakerConfigEntry = ConfigEntry[MonsterSpeakerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MonsterSpeakerConfigEntry) -> bool:
    """Set up a Monster speaker from a config entry."""
    coordinator = MonsterSpeakerCoordinator(hass, entry, entry.data[CONF_ADDRESS])
    entry.runtime_data = coordinator
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonsterSpeakerConfigEntry) -> bool:
    """Unload the speaker and stop its BLE connection."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.async_stop()
    return True
