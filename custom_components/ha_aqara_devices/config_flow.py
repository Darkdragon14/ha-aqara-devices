from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .api import AqaraApi
from .const import AREA_OPTIONS, CONF_BRIDGE_TOKEN, CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL, DOMAIN
from .options_flow import OptionsFlowHandler


NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required("account", default=defaults.get("account", "")): str,
            vol.Required("area", default=defaults.get("area", "EU")): vol.In(AREA_OPTIONS),
            vol.Required(CONF_BRIDGE_URL, default=defaults.get(CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)): NON_EMPTY_STRING,
            vol.Required(CONF_BRIDGE_TOKEN, default=defaults.get(CONF_BRIDGE_TOKEN, "")): NON_EMPTY_STRING,
        }
    )


def _auth_code_schema() -> vol.Schema:
    return vol.Schema({vol.Required("auth_code"): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._pending_input: dict[str, Any] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
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

        return self.async_show_form(step_id="user", data_schema=_user_schema(user_input), errors=errors)

    async def async_step_auth_code(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        pending = self._pending_input
        if pending is None:
            return await self.async_step_user()

        if user_input is not None:
            session = aiohttp_client.async_get_clientsession(self.hass)
            api = AqaraApi(pending["area"], session)
            try:
                token_data = await api.exchange_auth_code(user_input["auth_code"], pending["account"])
                result = token_data.get("result") or {}
                entry_data = {
                    "account": pending["account"],
                    "area": pending["area"],
                    CONF_BRIDGE_URL: pending[CONF_BRIDGE_URL].strip(),
                    CONF_BRIDGE_TOKEN: pending[CONF_BRIDGE_TOKEN].strip(),
                    "access_token": result.get("accessToken"),
                    "refresh_token": result.get("refreshToken"),
                    "open_id": result.get("openId"),
                    "expires_at": api.expires_at,
                }
                return self.async_create_entry(title="Aqara Devices", data=entry_data)
            except Exception:
                errors["base"] = "auth"

        return self.async_show_form(step_id="auth_code", data_schema=_auth_code_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()
