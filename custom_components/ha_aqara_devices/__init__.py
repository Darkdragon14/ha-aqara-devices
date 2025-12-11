from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .api import AqaraApi
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(entry.data["area"], session)

    try:
        await api.login(entry.data["username"], entry.data["password"])
        cameras = await api.get_cameras()
        if not cameras:
            raise ConfigEntryNotReady("No Aqara G3 cameras found")
        dids = [c["did"] for c in cameras]
        for did in dids:
            try:
                await api.get_device_states(did)
            except Exception as e:
                raise ConfigEntryNotReady(f"Probe failed for {did}: {e}") from e

    except ConfigEntryNotReady:
        raise
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "dids": dids,
        "cameras": cameras, 
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
