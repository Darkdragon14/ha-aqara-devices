from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import aiohttp_client

from .api import AqaraApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(entry.data["area"], session)

    try:
        await api.login(entry.data["username"], entry.data["password"])
    except Exception as e:
        raise HomeAssistantError(f"Aqara login failed: {e}")

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "did": entry.data["did"],
    }

    async def handle_set_video(call: ServiceCall) -> None:
        cfg = hass.data[DOMAIN][entry.entry_id]
        api: AqaraApi = cfg["api"]
        did: str = call.data.get("did") or cfg["did"]
        state = str(call.data.get("state")).lower()
        if state in ("1", "on", "true"):
            value = 1
        elif state in ("0", "off", "false"):
            value = 0
        else:
            raise HomeAssistantError("Invalid 'state'. Use 0/1 or 'off'/'on'.")

        payload = {"data": {"set_video": value}, "subjectId": did}
        data = await api.res_write(payload)
        if data.get("code") not in (0, "0"):
            raise HomeAssistantError(f"Aqara API error: {data}")
        _LOGGER.debug("set_video -> %s", data)

    hass.services.async_register(DOMAIN, "set_video", handle_set_video)

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True

async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    return

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "set_video")
    return True