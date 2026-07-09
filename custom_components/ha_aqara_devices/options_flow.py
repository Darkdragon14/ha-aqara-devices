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
    CONF_RTSP_CAMERAS,
    CONF_RTSP_ENABLED,
    CONF_RTSP_HOST,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PATH,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    DATA_RTSP_CANDIDATE_CAMERAS,
    DEFAULT_BRIDGE_URL,
    DEFAULT_RTSP_PATH,
    DEFAULT_RTSP_PORT,
    DOMAIN,
)


NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))
SECRET_TEXT = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
RTSP_PORT = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
CAMERA_ACTION_EDIT = "edit"
CAMERA_ACTION_REMOVE = "remove"
CAMERA_ACTIONS = {
    CAMERA_ACTION_EDIT: "Add or edit stream",
    CAMERA_ACTION_REMOVE: "Remove stream",
}


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
        self._selected_camera_did: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="init", menu_options=["account_bridge", "camera_streams"])

    async def async_step_account_bridge(self, user_input: dict[str, Any] | None = None):
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
                return await self._async_finish_options(dict(self.config_entry.options))

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
        return self.async_show_form(step_id="account_bridge", data_schema=_options_schema(defaults), errors=errors)

    async def async_step_auth_code(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        pending = self._pending_input
        if pending is None:
            return await self.async_step_account_bridge()

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
                return await self._async_finish_options(dict(self.config_entry.options))
            except Exception:
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="auth_code",
            data_schema=vol.Schema({vol.Required("auth_code"): str}),
            errors=errors,
        )

    def _runtime_entry_data(self) -> dict[str, Any] | None:
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    def _rtsp_candidates(self) -> list[dict[str, str]]:
        entry_data = self._runtime_entry_data()
        if entry_data is None:
            return []
        return list(entry_data.get(DATA_RTSP_CANDIDATE_CAMERAS, []))

    def _camera_by_did(self, did: str | None) -> dict[str, str] | None:
        if did is None:
            return None
        for camera in self._rtsp_candidates():
            if camera.get("did") == did:
                return camera
        return None

    @staticmethod
    def _camera_choice_label(camera: dict[str, str]) -> str:
        name = camera.get("deviceName") or camera["did"]
        label = camera.get("label") or camera.get("model") or "Aqara camera"
        return f"{name} ({label})"

    def _existing_rtsp_config(self, did: str) -> dict[str, Any]:
        cameras = self.config_entry.options.get(CONF_RTSP_CAMERAS, {})
        if not isinstance(cameras, dict):
            return {}
        config = cameras.get(did, {})
        return dict(config) if isinstance(config, dict) else {}

    def _camera_edit_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_RTSP_ENABLED, default=defaults.get(CONF_RTSP_ENABLED, True)): bool,
                vol.Required(CONF_RTSP_HOST, default=defaults.get(CONF_RTSP_HOST, "")): NON_EMPTY_STRING,
                vol.Required(CONF_RTSP_PORT, default=defaults.get(CONF_RTSP_PORT, DEFAULT_RTSP_PORT)): RTSP_PORT,
                vol.Optional(CONF_RTSP_USERNAME, default=defaults.get(CONF_RTSP_USERNAME, "")): str,
                vol.Optional(CONF_RTSP_PASSWORD, default=""): SECRET_TEXT,
                vol.Required(CONF_RTSP_PATH, default=defaults.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH)): NON_EMPTY_STRING,
            }
        )

    async def _async_finish_options(self, options: dict[str, Any]):
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="Aqara Devices", data=options)

    async def async_step_camera_streams(self, user_input: dict[str, Any] | None = None):
        if self._runtime_entry_data() is None:
            return self.async_show_form(
                step_id="camera_streams",
                data_schema=vol.Schema({}),
                errors={"base": "integration_not_loaded"},
            )

        cameras = self._rtsp_candidates()
        if not cameras:
            return self.async_show_form(
                step_id="camera_streams",
                data_schema=vol.Schema({}),
                errors={"base": "no_camera_devices"},
            )

        if user_input is not None:
            self._selected_camera_did = user_input["camera_did"]
            if user_input["action"] == CAMERA_ACTION_REMOVE:
                return await self.async_step_camera_remove()
            return await self.async_step_camera_edit()

        camera_choices = {camera["did"]: self._camera_choice_label(camera) for camera in cameras}
        return self.async_show_form(
            step_id="camera_streams",
            data_schema=vol.Schema(
                {
                    vol.Required("camera_did"): vol.In(camera_choices),
                    vol.Required("action", default=CAMERA_ACTION_EDIT): vol.In(CAMERA_ACTIONS),
                }
            ),
        )

    async def async_step_camera_edit(self, user_input: dict[str, Any] | None = None):
        camera = self._camera_by_did(self._selected_camera_did)
        if camera is None:
            return self.async_show_form(
                step_id="camera_edit",
                data_schema=vol.Schema({}),
                errors={"base": "camera_not_found"},
            )

        did = camera["did"]
        existing = self._existing_rtsp_config(did)
        from .camera_config import can_save_rtsp_camera_config, normalize_rtsp_camera_config

        defaults = normalize_rtsp_camera_config(existing)
        errors: dict[str, str] = {}

        if user_input is not None:
            password = str(user_input.get(CONF_RTSP_PASSWORD, "")).strip()
            if not password and existing.get(CONF_RTSP_PASSWORD):
                password = str(existing[CONF_RTSP_PASSWORD]).strip()

            rtsp_input = {
                CONF_RTSP_ENABLED: user_input[CONF_RTSP_ENABLED],
                CONF_RTSP_HOST: user_input[CONF_RTSP_HOST],
                CONF_RTSP_PORT: user_input[CONF_RTSP_PORT],
                CONF_RTSP_USERNAME: user_input.get(CONF_RTSP_USERNAME, ""),
                CONF_RTSP_PASSWORD: password,
                CONF_RTSP_PATH: user_input[CONF_RTSP_PATH],
            }
            updated_config = normalize_rtsp_camera_config(rtsp_input)
            if not can_save_rtsp_camera_config(rtsp_input):
                errors["base"] = "invalid_rtsp"
            else:
                options = dict(self.config_entry.options)
                current_rtsp_cameras = options.get(CONF_RTSP_CAMERAS, {})
                rtsp_cameras = dict(current_rtsp_cameras) if isinstance(current_rtsp_cameras, dict) else {}
                rtsp_cameras[did] = updated_config
                options[CONF_RTSP_CAMERAS] = rtsp_cameras
                return await self._async_finish_options(options)

        return self.async_show_form(
            step_id="camera_edit",
            data_schema=self._camera_edit_schema(defaults),
            errors=errors,
        )

    async def async_step_camera_remove(self, user_input: dict[str, Any] | None = None):
        camera = self._camera_by_did(self._selected_camera_did)
        if camera is None:
            return self.async_show_form(
                step_id="camera_remove",
                data_schema=vol.Schema({}),
                errors={"base": "camera_not_found"},
            )

        if user_input is not None:
            if not user_input.get("confirm_remove"):
                return await self.async_step_camera_streams()

            options = dict(self.config_entry.options)
            current_rtsp_cameras = options.get(CONF_RTSP_CAMERAS, {})
            rtsp_cameras = dict(current_rtsp_cameras) if isinstance(current_rtsp_cameras, dict) else {}
            rtsp_cameras.pop(camera["did"], None)
            options[CONF_RTSP_CAMERAS] = rtsp_cameras
            return await self._async_finish_options(options)

        return self.async_show_form(
            step_id="camera_remove",
            data_schema=vol.Schema({vol.Required("confirm_remove", default=False): bool}),
        )
