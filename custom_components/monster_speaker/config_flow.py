"""Config flow for Monster BLE speakers."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN, SERVICE_UUID

_NAME_PREFIX = "RR270"


def _normalize_address(value: str) -> str:
    """Validate and normalize a Bluetooth MAC address, raising ValueError if invalid."""
    address = value.strip().replace("-", ":").upper()
    parts = address.split(":")
    if len(parts) != 6 or any(
        len(part) != 2 or any(character not in "0123456789ABCDEF" for character in part)
        for part in parts
    ):
        raise ValueError("invalid Bluetooth address")
    return format_mac(address)


def _clean_name(name: str | None) -> str:
    return (name or "").replace("\x00", "").strip() or "Monster Speaker"


def _is_monster(info: BluetoothServiceInfoBleak) -> bool:
    return SERVICE_UUID in info.service_uuids or _clean_name(info.name).startswith(_NAME_PREFIX)


class MonsterSpeakerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Discover or manually configure a Monster speaker."""

    VERSION = 1

    def __init__(self) -> None:
        self._address: str | None = None
        self._name: str = "Monster Speaker"
        self._discovered: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device discovered by its advertised service UUID."""
        if not discovery_info.connectable or not _is_monster(discovery_info):
            return self.async_abort(reason="unsupported_device")

        address = format_mac(discovery_info.address)
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        self._address = address
        self._name = _clean_name(discovery_info.name)
        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the discovered speaker."""
        if user_input is not None:
            return self._create_entry()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a speaker HA currently hears, or enter its MAC address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                address = _normalize_address(user_input[CONF_ADDRESS])
            except ValueError:
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                if (
                    bluetooth.async_ble_device_from_address(
                        self.hass, address.upper(), connectable=True
                    )
                    is None
                ):
                    errors[CONF_ADDRESS] = "device_not_seen"
                else:
                    self._address = address
                    self._name = self._discovered.get(
                        address, "Monster Speaker"
                    ).split(" (")[0]
                    return self._create_entry()

        configured = self._async_current_ids(include_ignore=False)
        self._discovered = {
            format_mac(info.address): f"{_clean_name(info.name)} ({info.address})"
            for info in bluetooth.async_discovered_service_info(self.hass, connectable=True)
            if _is_monster(info) and format_mac(info.address) not in configured
        }
        if self._discovered:
            schema = vol.Schema({vol.Required(CONF_ADDRESS): vol.In(self._discovered)})
        else:
            schema = vol.Schema({vol.Required(CONF_ADDRESS): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _create_entry(self) -> ConfigFlowResult:
        assert self._address is not None
        return self.async_create_entry(
            title=f"Monster Speaker ({self._name})",
            data={CONF_ADDRESS: self._address},
        )