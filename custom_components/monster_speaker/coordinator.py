"""Maintain the Monster speaker's BLE connection and send captured commands."""

from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    MAX_VOLUME_STEP,
    POWER_OFF_COMMAND,
    POWER_ON_COMMAND,
    POWER_UUID,
    VOLUME_UUID,
)

_LOGGER = logging.getLogger(__name__)
_RECONNECT_DELAY = 5


def _reverse_uuid(uuid: str) -> str:
    """Return a 128-bit UUID with its byte order reversed."""
    raw = bytes.fromhex(uuid.replace("-", ""))[::-1].hex()
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


class MonsterSpeakerCoordinator(DataUpdateCoordinator[dict[str, object]]):
    """Keep a BLE connection open for speaker control."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, address: str) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}_{address}")
        self.address = address.upper()
        self.data: dict[str, object] = {
            "connected": False,
            "is_on": None,
            "volume": None,
            "characteristics": [],
        }
        self._ble_device: BLEDevice | None = None
        self._client: BleakClient | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._advertisement = asyncio.Event()
        self._disconnected = asyncio.Event()
        self._unsub_bluetooth = None

    async def async_start(self) -> None:
        """Begin discovery and the reconnect loop."""
        self._unsub_bluetooth = bluetooth.async_register_callback(
            self.hass,
            self._handle_advertisement,
            BluetoothCallbackMatcher(address=self.address, connectable=True),
            BluetoothScanningMode.ACTIVE,
        )
        self._ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        self._task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_connection_loop(),
            name=f"{DOMAIN}_{self.address}_connection",
        )

    async def async_stop(self) -> None:
        """Stop discovery, connection loop, and BLE client."""
        self._stop.set()
        if self._unsub_bluetooth:
            self._unsub_bluetooth()
            self._unsub_bluetooth = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._disconnect()

    @callback
    def _handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak, _change: BluetoothChange
    ) -> None:
        if service_info.device is not None:
            self._ble_device = service_info.device
            self._advertisement.set()

    @callback
    def _handle_disconnect(self, _client: BleakClient) -> None:
        self._disconnected.set()

    async def async_command(self, characteristic: str, payload: bytes) -> None:
        """Write a captured command over the coordinator-owned connection."""
        client = self._client
        if client is None or not client.is_connected:
            raise BleakError("Speaker is not connected")
        char = client.services.get_characteristic(characteristic)
        if char is None:
            # The vendor UUIDs look byte-reversed; accept either byte order.
            char = client.services.get_characteristic(_reverse_uuid(characteristic))
        if char is None:
            raise BleakError(
                f"Characteristic {characteristic} not found on speaker; it exposes: "
                + "; ".join(self.data.get("characteristics") or ["(none)"])
            )
        # Use write-without-response only when the characteristic offers it.
        response = "write-without-response" not in char.properties
        _LOGGER.debug(
            "Write %s -> %s (response=%s)", payload.hex(" "), char.uuid, response
        )
        await client.write_gatt_char(char, payload, response=response)

    async def async_power(self, turn_on: bool) -> None:
        """Send the captured power command and optimistically update state."""
        await self.async_command(POWER_UUID, POWER_ON_COMMAND if turn_on else POWER_OFF_COMMAND)
        self.data["is_on"] = turn_on
        self.async_set_updated_data(self.data)

    async def async_set_volume(self, volume: float) -> None:
        """Set volume using the app-observed 0-32 protocol scale."""
        step = max(0, min(MAX_VOLUME_STEP, round(volume * MAX_VOLUME_STEP)))
        await self.async_command(VOLUME_UUID, bytes((step, 0, 0)))
        self.data["volume"] = step / MAX_VOLUME_STEP
        self.async_set_updated_data(self.data)

    async def async_volume_step(self, up: bool) -> None:
        """Move volume one protocol step (1/32) up or down.

        The speaker does not report its volume, so stepping is only offered
        once a level has been set from Home Assistant. Guessing a starting
        level could cause a sudden loud jump.
        """
        current = self.data.get("volume")
        if current is None:
            raise HomeAssistantError(
                "Set a volume level first; the speaker does not report its current volume"
            )
        step = round(float(current) * MAX_VOLUME_STEP)
        step = max(0, min(MAX_VOLUME_STEP, step + (1 if up else -1)))
        await self.async_set_volume(step / MAX_VOLUME_STEP)

    async def _async_connection_loop(self) -> None:
        """Connect when available and reconnect after peripheral disconnects."""
        while not self._stop.is_set():
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            ) or self._ble_device
            if device is None:
                _LOGGER.debug(
                    "No connectable advertisement from %s yet; waiting", self.address
                )
                self._advertisement.clear()
                try:
                    await asyncio.wait_for(self._advertisement.wait(), timeout=30)
                except TimeoutError:
                    continue
                continue
            self._disconnected.clear()
            try:
                self._client = await establish_connection(
                    BleakClient,
                    device,
                    f"Monster Speaker {self.address}",
                    disconnected_callback=self._handle_disconnect,
                    max_attempts=3,
                )
                self.data["characteristics"] = [
                    f"{char.uuid} [{','.join(char.properties)}]"
                    for service in self._client.services
                    for char in service.characteristics
                ]
                _LOGGER.debug(
                    "Connected to %s; characteristics: %s",
                    self.address,
                    self.data["characteristics"],
                )
                self.data["connected"] = True
                self.async_set_updated_data(self.data)
                await self._disconnected.wait()
            except asyncio.CancelledError:
                raise
            except (BleakError, OSError, TimeoutError) as err:
                _LOGGER.debug("BLE connection to %s failed: %s", self.address, err)
                # Drop the cached device so the next attempt waits for a fresh
                # advertisement instead of hammering a device that is gone.
                self._ble_device = None
            except Exception:
                _LOGGER.exception("Unexpected Monster speaker connection error")
                self._ble_device = None
            finally:
                self.data["connected"] = False
                self.async_set_updated_data(self.data)
                await self._disconnect()
            if not self._stop.is_set():
                await asyncio.sleep(_RECONNECT_DELAY)

    async def _disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except (BleakError, OSError):
                _LOGGER.debug("Error disconnecting from %s", self.address, exc_info=True)
