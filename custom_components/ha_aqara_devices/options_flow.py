from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import (
    AREA_OPTIONS,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_KEY_ID,
    DEFAULT_BRIDGE_URL,
)


NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))
SECRET_TEXT = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("account", default=defaults.get("account", "")): str,
            vol.Required("area", default=defaults.get("area", "EU")): vol.In(AREA_OPTIONS),
            vol.Required(CONF_BRIDGE_URL, default=defaults.get(CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)): NON_EMPTY_STRING,
            vol.Required(CONF_BRIDGE_TOKEN, default=defaults.get(CONF_BRIDGE_TOKEN, "")): SECRET_TEXT,
            vol.Required(CONF_APP_ID, default=defaults.get(CONF_APP_ID, "")): NON_EMPTY_STRING,
            vol.Required(CONF_APP_KEY, default=defaults.get(CONF_APP_KEY, "")): SECRET_TEXT,
            vol.Required(CONF_KEY_ID, default=defaults.get(CONF_KEY_ID, "")): SECRET_TEXT,
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
                CONF_APP_ID: user_input[CONF_APP_ID].strip(),
                CONF_KEY_ID: user_input[CONF_KEY_ID].strip(),
                CONF_APP_KEY: user_input[CONF_APP_KEY].strip(),
            }
            account_changed = user_input["account"] != self.config_entry.data.get("account")
            area_changed = user_input["area"] != self.config_entry.data.get("area")
            app_id_changed = user_input[CONF_APP_ID].strip() != str(self.config_entry.data.get(CONF_APP_ID, "")).strip()
            key_id_changed = user_input[CONF_KEY_ID].strip() != str(self.config_entry.data.get(CONF_KEY_ID, "")).strip()
            app_key_changed = user_input[CONF_APP_KEY].strip() != str(self.config_entry.data.get(CONF_APP_KEY, "")).strip()
            if not account_changed and not area_changed and not app_id_changed and not key_id_changed and not app_key_changed:
                self.hass.config_entries.async_update_entry(self.config_entry, data=updated_data)
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="Aqara Devices", data={})

            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                from .api import AqaraApi

                api = AqaraApi(
                    user_input["area"],
                    session,
                    app_id=user_input[CONF_APP_ID],
                    app_key=user_input[CONF_APP_KEY],
                    key_id=user_input[CONF_KEY_ID],
                )
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
            CONF_APP_ID: self.config_entry.data.get(CONF_APP_ID, ""),
            CONF_KEY_ID: self.config_entry.data.get(CONF_KEY_ID, ""),
            CONF_APP_KEY: self.config_entry.data.get(CONF_APP_KEY, ""),
        }
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults), errors=errors)

    async def async_step_auth_code(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        pending = self._pending_input
        if pending is None:
            return await self.async_step_init()

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                from .api import AqaraApi

                api = AqaraApi(
                    pending["area"],
                    session,
                    app_id=pending[CONF_APP_ID],
                    app_key=pending[CONF_APP_KEY],
                    key_id=pending[CONF_KEY_ID],
                )
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
                        CONF_APP_ID: pending[CONF_APP_ID].strip(),
                        CONF_KEY_ID: pending[CONF_KEY_ID].strip(),
                        CONF_APP_KEY: pending[CONF_APP_KEY].strip(),
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
