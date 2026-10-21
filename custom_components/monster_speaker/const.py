"""Constants for the Monster RR270-X speaker integration."""

from homeassistant.const import Platform

DOMAIN = "monster_speaker"
PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

CONF_ADDRESS = "address"

SERVICE_UUID = "616b445f-a99d-c28d-3045-11a4d0ff0000"
# Characteristic UUIDs exactly as the speaker's GATT table reports them. The
# capture tool had shown these with each UUID field byte-swapped
# (d1ff0000-99eb-e746-7aa0-d3b2faf493f7 / d3ff0000-542c-46c5-9569-94eeb452ce00).
POWER_UUID = "f793f4fa-b2d3-7aa0-e746-99ebd1ff0000"
VOLUME_UUID = "00ce52b4-ee94-6995-c546-2c54d3ff0000"

# Captured from the Monster RR270-X app's GATT writes. Power mapping is
# provisional: the two writes were observed in sequence, but not timestamped
# against an explicit user action in the capture.
POWER_ON_COMMAND = bytes.fromhex("80 FA EA 00")
POWER_OFF_COMMAND = bytes.fromhex("80 AE BF 00")
MAX_VOLUME_STEP = 32
