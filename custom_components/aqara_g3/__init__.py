from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import aiohttp_client

from .api import AqaraApi
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(entry.data["area"], session)

    try:
        await api.login(entry.data["username"], entry.data["password"])
        # Probe state once so we can fail fast with ConfigEntryNotReady
        did = entry.data["did"]
        await api.get_device_states(did)
    except ConfigEntryNotReady:
        raise
    except Exception as e:
        # If we cannot reach/query state now, tell HA to retry later
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "did": entry.data["did"],
    }

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
