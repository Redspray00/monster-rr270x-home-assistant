"""Media-player entity for captured Monster speaker controls."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MonsterSpeakerConfigEntry
from .const import DOMAIN
from .coordinator import MonsterSpeakerCoordinator

_BASE_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MonsterSpeakerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the speaker media player."""
    async_add_entities([MonsterSpeakerMediaPlayer(entry.runtime_data, entry)])


class MonsterSpeakerMediaPlayer(
    CoordinatorEntity[MonsterSpeakerCoordinator], MediaPlayerEntity
):
    """Expose power and volume; Bluetooth audio streaming is not provided."""

    _attr_has_entity_name = True
    _attr_name = "Speaker"
    # The speaker never reports power or volume back, so state is optimistic.
    _attr_assumed_state = True
    _attr_should_poll = False
    # Diagnostic detail; keep it out of the recorder database.
    _unrecorded_attributes = frozenset({"gatt_characteristics"})

    def __init__(
        self, coordinator: MonsterSpeakerCoordinator, entry: MonsterSpeakerConfigEntry
    ) -> None:
        super().__init__(coordinator)
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = address.lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address.upper())},
            connections={(CONNECTION_BLUETOOTH, address.upper())},
            name="Monster RR270-X",
            manufacturer="Monster",
            model="RR270-X",
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.get("connected"))

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Offer volume steps only once a level is known, to avoid loud jumps."""
        if self.coordinator.data.get("volume") is None:
            return _BASE_FEATURES
        return _BASE_FEATURES | MediaPlayerEntityFeature.VOLUME_STEP

    @property
    def state(self) -> MediaPlayerState | None:
        is_on = self.coordinator.data.get("is_on")
        if is_on is None:
            # The speaker only advertises and accepts BLE while powered, so a
            # live connection with no confirmed power state means it is on.
            return MediaPlayerState.ON
        return MediaPlayerState.ON if is_on else MediaPlayerState.OFF

    @property
    def icon(self) -> str:
        return "mdi:speaker" if self.state == MediaPlayerState.ON else "mdi:speaker-off"

    @property
    def volume_level(self) -> float | None:
        return self.coordinator.data.get("volume")  # type: ignore[return-value]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"gatt_characteristics": self.coordinator.data.get("characteristics") or []}

    async def async_turn_on(self) -> None:
        await self.coordinator.async_power(True)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_power(False)

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_set_volume(volume)

    async def async_volume_up(self) -> None:
        await self.coordinator.async_volume_step(True)

    async def async_volume_down(self) -> None:
        await self.coordinator.async_volume_step(False)