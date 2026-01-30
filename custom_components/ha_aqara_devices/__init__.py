from __future__ import annotations
import logging
from typing import Any

from importlib import import_module

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .api import AqaraApi
from .const import DOMAIN, PLATFORMS, G3_MODEL, FP2_MODEL

# Preload platform modules so Home Assistant doesn't import them inside the event loop
for _platform in PLATFORMS:
    import_module(f".{_platform}", __package__)

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
        devices = await api.get_devices()
        cameras = [device for device in devices if device.get("model") == G3_MODEL]
        fp2_devices = [device for device in devices if device.get("model") == FP2_MODEL]
        if not cameras and not fp2_devices:
            raise ConfigEntryNotReady("No Aqara G3 or FP2 devices found")

        for cam in cameras:
            did = cam["did"]
            try:
                await api.get_device_states(did)
            except Exception as e:
                raise ConfigEntryNotReady(f"G3 probe failed for {did}: {e}") from e

        for fp2 in fp2_devices:
            did = fp2["did"]
            try:
                await api.get_fp2_full_state(did)
            except Exception as e:
                raise ConfigEntryNotReady(f"FP2 probe failed for {did}: {e}") from e

    except ConfigEntryNotReady:
        raise
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "cameras": cameras, 
        "fp2_devices": fp2_devices,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
