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
    CONF_CAMERA_STREAMS,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_URL,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_HOMEKIT_ID,
    CONF_MANAGED_HOMEKIT,
    CONF_STREAM_NAME,
    DATA_CAMERA_CANDIDATES,
    DEFAULT_BRIDGE_URL,
    DEFAULT_GO2RTC_RTSP_URL,
    DEFAULT_GO2RTC_URL,
    DOMAIN,
)


NON_EMPTY_STRING = vol.All(str, vol.Length(min=1))
SECRET_TEXT = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
CAMERA_ACTION_CONFIGURE = "configure"
CAMERA_ACTION_REMOVE = "remove"
CAMERA_ACTIONS = {
    CAMERA_ACTION_CONFIGURE: "Add or replace stream",
    CAMERA_ACTION_REMOVE: "Remove stream",
}
CAMERA_SOURCE_PAIR = "pair"
CAMERA_SOURCE_EXISTING = "existing"
CAMERA_SOURCES = {
    CAMERA_SOURCE_PAIR: "Pair a discovered HomeKit camera",
    CAMERA_SOURCE_EXISTING: "Use an existing go2rtc stream",
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
        self._discovered_homekit: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="init", menu_options=["account_bridge", "go2rtc", "camera_streams"])

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

    def _camera_candidates(self) -> list[dict[str, str]]:
        entry_data = self._runtime_entry_data()
        if entry_data is None:
            return []
        return list(entry_data.get(DATA_CAMERA_CANDIDATES, []))

    def _camera_by_did(self, did: str | None) -> dict[str, str] | None:
        if did is None:
            return None
        for camera in self._camera_candidates():
            if camera.get("did") == did:
                return camera
        return None

    @staticmethod
    def _camera_choice_label(camera: dict[str, str]) -> str:
        name = camera.get("deviceName") or camera["did"]
        label = camera.get("label") or camera.get("model") or "Aqara camera"
        return f"{name} ({label})"

    def _existing_stream_config(self, did: str) -> dict[str, Any]:
        cameras = self.config_entry.options.get(CONF_CAMERA_STREAMS, {})
        if not isinstance(cameras, dict):
            return {}
        config = cameras.get(did, {})
        return dict(config) if isinstance(config, dict) else {}

    def _go2rtc_client(self, options: dict[str, Any] | None = None):
        from .go2rtc_client import Go2RtcClient

        values = options or dict(self.config_entry.options)
        session = aiohttp_client.async_get_clientsession(self.hass)
        return Go2RtcClient(
            session,
            str(values.get(CONF_GO2RTC_URL, "")),
            str(values.get(CONF_GO2RTC_USERNAME, "")),
            str(values.get(CONF_GO2RTC_PASSWORD, "")),
        )

    def _go2rtc_is_configured(self) -> bool:
        return bool(
            str(self.config_entry.options.get(CONF_GO2RTC_URL, "")).strip()
            and str(self.config_entry.options.get(CONF_GO2RTC_RTSP_URL, "")).strip()
        )

    def _save_camera_stream(self, did: str, config: dict[str, Any]) -> dict[str, Any]:
        options = dict(self.config_entry.options)
        current = options.get(CONF_CAMERA_STREAMS, {})
        streams = dict(current) if isinstance(current, dict) else {}
        streams[did] = config
        options[CONF_CAMERA_STREAMS] = streams
        return options

    async def _async_finish_options(self, options: dict[str, Any]):
        self.hass.config_entries.async_update_entry(self.config_entry, options=options)
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)
        return self.async_create_entry(title="Aqara Devices", data=options)

    async def async_step_go2rtc(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        existing = self.config_entry.options

        if user_input is not None:
            from .camera_config import build_rtsp_stream_url, has_managed_camera_streams

            username = str(user_input.get(CONF_GO2RTC_USERNAME, "")).strip()
            password = str(user_input.get(CONF_GO2RTC_PASSWORD, "")).strip()
            if user_input.get("clear_go2rtc_credentials"):
                username = ""
                password = ""
            elif not password and username == str(existing.get(CONF_GO2RTC_USERNAME, "")).strip():
                password = str(existing.get(CONF_GO2RTC_PASSWORD, "")).strip()
            updated = {
                **existing,
                CONF_GO2RTC_URL: str(user_input[CONF_GO2RTC_URL]).strip().rstrip("/"),
                CONF_GO2RTC_USERNAME: username,
                CONF_GO2RTC_PASSWORD: password,
                CONF_GO2RTC_RTSP_URL: str(user_input[CONF_GO2RTC_RTSP_URL]).strip().rstrip("/"),
            }
            current_api_url = str(existing.get(CONF_GO2RTC_URL, "")).strip().rstrip("/")
            camera_streams = existing.get(CONF_CAMERA_STREAMS, {})
            if (
                current_api_url
                and updated[CONF_GO2RTC_URL] != current_api_url
                and has_managed_camera_streams(camera_streams)
            ):
                errors["base"] = "remove_managed_streams_before_go2rtc_change"
            else:
                try:
                    await self._go2rtc_client(updated).validate()
                except Exception:
                    errors["base"] = "go2rtc_connection"
                else:
                    if build_rtsp_stream_url(updated[CONF_GO2RTC_RTSP_URL], "validation") is None:
                        errors["base"] = "invalid_go2rtc_rtsp_url"
                    else:
                        return await self._async_finish_options(updated)

        return self.async_show_form(
            step_id="go2rtc",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_GO2RTC_URL,
                        default=existing.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL),
                    ): NON_EMPTY_STRING,
                    vol.Optional(
                        CONF_GO2RTC_USERNAME,
                        default=existing.get(CONF_GO2RTC_USERNAME, ""),
                    ): str,
                    vol.Optional(CONF_GO2RTC_PASSWORD, default=""): SECRET_TEXT,
                    vol.Optional("clear_go2rtc_credentials", default=False): bool,
                    vol.Required(
                        CONF_GO2RTC_RTSP_URL,
                        default=existing.get(CONF_GO2RTC_RTSP_URL, DEFAULT_GO2RTC_RTSP_URL),
                    ): NON_EMPTY_STRING,
                }
            ),
            errors=errors,
        )

    async def async_step_camera_streams(self, user_input: dict[str, Any] | None = None):
        if self._runtime_entry_data() is None:
            return self.async_show_form(
                step_id="camera_streams",
                data_schema=vol.Schema({}),
                errors={"base": "integration_not_loaded"},
            )

        if not self._go2rtc_is_configured():
            return self.async_show_form(
                step_id="camera_streams",
                data_schema=vol.Schema({}),
                errors={"base": "go2rtc_not_configured"},
            )

        cameras = self._camera_candidates()
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
            return await self.async_step_camera_source()

        camera_choices = {camera["did"]: self._camera_choice_label(camera) for camera in cameras}
        return self.async_show_form(
            step_id="camera_streams",
            data_schema=vol.Schema(
                {
                    vol.Required("camera_did"): vol.In(camera_choices),
                    vol.Required("action", default=CAMERA_ACTION_CONFIGURE): vol.In(CAMERA_ACTIONS),
                }
            ),
        )

    async def async_step_camera_source(self, user_input: dict[str, Any] | None = None):
        camera = self._camera_by_did(self._selected_camera_did)
        if camera is None:
            return self.async_show_form(
                step_id="camera_source",
                data_schema=vol.Schema({}),
                errors={"base": "camera_not_found"},
            )

        existing = self._existing_stream_config(camera["did"])
        if existing.get(CONF_MANAGED_HOMEKIT):
            return self.async_show_form(
                step_id="camera_source",
                data_schema=vol.Schema({}),
                errors={"base": "remove_managed_stream_first"},
            )

        if user_input is not None:
            if user_input["source_mode"] == CAMERA_SOURCE_EXISTING:
                return await self.async_step_camera_existing()
            return await self.async_step_camera_pair()

        return self.async_show_form(
            step_id="camera_source",
            data_schema=vol.Schema(
                {vol.Required("source_mode", default=CAMERA_SOURCE_PAIR): vol.In(CAMERA_SOURCES)}
            ),
        )

    async def async_step_camera_pair(self, user_input: dict[str, Any] | None = None):
        camera = self._camera_by_did(self._selected_camera_did)
        if camera is None:
            return self.async_show_form(
                step_id="camera_pair", data_schema=vol.Schema({}), errors={"base": "camera_not_found"}
            )

        from .camera_config import stream_name_for_did

        errors: dict[str, str] = {}
        client = self._go2rtc_client()
        if user_input is not None:
            source = str(user_input["homekit_source"])
            try:
                await client.pair_homekit(
                    stream_name_for_did(camera["did"]),
                    source,
                    str(user_input["homekit_pin"]).strip(),
                )
            except Exception:
                errors["base"] = "homekit_pairing"
            else:
                stream_name = stream_name_for_did(camera["did"])
                options = self._save_camera_stream(
                    camera["did"],
                    {
                        CONF_STREAM_NAME: stream_name,
                        CONF_MANAGED_HOMEKIT: True,
                        CONF_HOMEKIT_ID: stream_name,
                    },
                )
                return await self._async_finish_options(options)

        try:
            discovered = await client.discover_homekit()
            self._discovered_homekit = {item.url: item.name for item in discovered}
        except Exception:
            errors["base"] = "go2rtc_connection"
            self._discovered_homekit = {}

        if not self._discovered_homekit and not errors:
            errors["base"] = "no_homekit_cameras"

        return self.async_show_form(
            step_id="camera_pair",
            data_schema=vol.Schema(
                {
                    vol.Required("homekit_source"): vol.In(self._discovered_homekit),
                    vol.Required("homekit_pin"): SECRET_TEXT,
                }
            ),
            errors=errors,
        )

    async def async_step_camera_existing(self, user_input: dict[str, Any] | None = None):
        camera = self._camera_by_did(self._selected_camera_did)
        if camera is None:
            return self.async_show_form(
                step_id="camera_existing", data_schema=vol.Schema({}), errors={"base": "camera_not_found"}
            )

        errors: dict[str, str] = {}
        try:
            streams = await self._go2rtc_client().list_streams()
        except Exception:
            streams = []
            errors["base"] = "go2rtc_connection"

        if user_input is not None and not errors:
            stream_name = str(user_input[CONF_STREAM_NAME])
            options = self._save_camera_stream(
                camera["did"],
                {
                    CONF_STREAM_NAME: stream_name,
                    CONF_MANAGED_HOMEKIT: False,
                    CONF_HOMEKIT_ID: "",
                },
            )
            return await self._async_finish_options(options)

        if not streams and not errors:
            errors["base"] = "no_go2rtc_streams"
        choices = {name: name for name in streams}
        return self.async_show_form(
            step_id="camera_existing",
            data_schema=vol.Schema({vol.Required(CONF_STREAM_NAME): vol.In(choices)}),
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

        existing = self._existing_stream_config(camera["did"])
        managed = bool(existing.get(CONF_MANAGED_HOMEKIT))
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get("confirm_remove"):
                return await self.async_step_camera_streams()

            if managed and user_input.get("unpair_homekit"):
                try:
                    await self._go2rtc_client().unpair_homekit(
                        str(existing.get(CONF_HOMEKIT_ID) or existing.get(CONF_STREAM_NAME))
                    )
                except Exception:
                    errors["base"] = "homekit_unpairing"

            if errors:
                return self.async_show_form(
                    step_id="camera_remove",
                    data_schema=vol.Schema(
                        {
                            vol.Required("confirm_remove", default=True): bool,
                            vol.Required("unpair_homekit", default=True): bool,
                        }
                    ),
                    errors=errors,
                )

            options = dict(self.config_entry.options)
            current_streams = options.get(CONF_CAMERA_STREAMS, {})
            camera_streams = dict(current_streams) if isinstance(current_streams, dict) else {}
            camera_streams.pop(camera["did"], None)
            options[CONF_CAMERA_STREAMS] = camera_streams
            return await self._async_finish_options(options)

        fields: dict[Any, Any] = {vol.Required("confirm_remove", default=False): bool}
        if managed:
            fields[vol.Required("unpair_homekit", default=True)] = bool
        return self.async_show_form(
            step_id="camera_remove",
            data_schema=vol.Schema(fields),
        )
