"""Diagnostics for the Monster RR270-X speaker, with the MAC address redacted."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import MonsterSpeakerConfigEntry

TO_REDACT = {CONF_ADDRESS, "address", "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MonsterSpeakerConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "state": {
            "connected": coordinator.data.get("connected"),
            "is_on": coordinator.data.get("is_on"),
            "volume": coordinator.data.get("volume"),
        },
        "gatt_characteristics": coordinator.data.get("characteristics") or [],
    }
