from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .api import AqaraApi
from .const import AREA_OPTIONS, CONF_BRIDGE_TOKEN, CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL


NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("account", default=defaults.get("account", "")): str,
            vol.Required("area", default=defaults.get("area", "EU")): vol.In(AREA_OPTIONS),
            vol.Required(CONF_BRIDGE_URL, default=defaults.get(CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)): NON_EMPTY_STRING,
            vol.Required(CONF_BRIDGE_TOKEN, default=defaults.get(CONF_BRIDGE_TOKEN, "")): NON_EMPTY_STRING,
        }
    )


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._pending_input: dict[str, Any] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            updated_data = {
                **self.config_entry.data,
                CONF_BRIDGE_URL: user_input[CONF_BRIDGE_URL].strip(),
                CONF_BRIDGE_TOKEN: user_input[CONF_BRIDGE_TOKEN].strip(),
            }
            account_changed = user_input["account"] != self.config_entry.data.get("account")
            area_changed = user_input["area"] != self.config_entry.data.get("area")
            if not account_changed and not area_changed:
                self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="Aqara Devices", data={})

            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AqaraApi(user_input["area"], session)
            try:
                data = await api.request_auth_code(user_input["account"])
                if str(data.get("code")) != "0":
                    raise RuntimeError(data)
                self._pending_input = user_input
                return await self.async_step_auth_code()
            except Exception:
                errors["base"] = "auth"

        defaults = {
            "account": self.config_entry.data.get("account", ""),
            "area": self.config_entry.data.get("area", "EU"),
            CONF_BRIDGE_URL: self.config_entry.data.get(CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL),
            CONF_BRIDGE_TOKEN: self.config_entry.data.get(CONF_BRIDGE_TOKEN, ""),
        }
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults), errors=errors)

    async def async_step_auth_code(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        pending = self._pending_input
        if pending is None:
            return await self.async_step_init()

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AqaraApi(pending["area"], session)
            try:
                token_data = await api.exchange_auth_code(user_input["auth_code"], pending["account"])
                result = token_data.get("result") or {}
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        "account": pending["account"],
                        "area": pending["area"],
                        CONF_BRIDGE_URL: pending[CONF_BRIDGE_URL].strip(),
                        CONF_BRIDGE_TOKEN: pending[CONF_BRIDGE_TOKEN].strip(),
                        "access_token": result.get("accessToken"),
                        "refresh_token": result.get("refreshToken"),
                        "open_id": result.get("openId"),
                        "expires_at": api.expires_at,
                    },
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="Aqara Devices", data={})
            except Exception:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="auth_code",
            data_schema=vol.Schema({vol.Required("auth_code"): str}),
            errors=errors,
        )
