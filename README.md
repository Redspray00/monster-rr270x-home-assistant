# Monster RR270-X Home Assistant Integration

Local Bluetooth Low Energy power and volume controls for the Monster RR270-X. This integration provides a media player entity for device controls; it does not stream Bluetooth audio or provide playback and track metadata.

## Requirements and installation

- Home Assistant with a connectable Bluetooth adapter or a nearby ESPHome Bluetooth proxy.
- Add this repository to HACS as a custom integration, then install **Monster Speaker**. Alternatively, copy `custom_components/monster_speaker` into `/config/custom_components/monster_speaker`.
- Close the Monster mobile app before connecting Home Assistant so it releases the speaker.
- Restart Home Assistant and add the discovered integration from **Settings → Devices & services**.

## Protocol and limitations

Volume writes use a three-byte payload `[step, 0, 0]`; captured app values ranged from 0 through 32. The power characteristic accepts the captured payloads `80 FA EA 00` and `80 AE BF 00`.

**Power mapping is provisional.** The capture did not correlate each power payload with a timestamped user action. The entity updates optimistically after writes, and confirmed power-state feedback has not been established. Use power control with that limitation in mind. BLE control does not carry audio.

Because the speaker reports neither power nor volume back over BLE, the entity is marked as *assumed state* and shows separate on/off buttons. The speaker appears to accept BLE connections only while powered, so after turning it off the entity becomes unavailable and turning it back on from Home Assistant may not be possible; use the speaker's own button.

Volume up/down buttons appear only after you have set a volume level from Home Assistant at least once since startup. This prevents a step from a guessed level causing a sudden loud jump.

## Diagnostics

**Settings → Devices & services → Monster Speaker → Download diagnostics** produces a report with the Bluetooth MAC address redacted, suitable for attaching to an issue.

The captured service UUID is `616b445f-a99d-c28d-3045-11a4d0ff0000`. Discovery uses the service advertisement; no speaker MAC address is required in the repository.

## License

Released under the [MIT License](LICENSE).
