from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .api import AqaraApi
from .binary_sensors import ALL_BINARY_SENSORS_DEF, M3_BINARY_SENSORS_DEF
from .numbers import ALL_NUMBERS_DEF, M3_NUMBERS_DEF
from .sensors import M3_SENSORS_DEF
from .selects import M3_SELECTS_DEF
from .switches import ALL_SWITCHES_DEF
from .const import DOMAIN, PLATFORMS, G3_MODEL, M3_MODELS

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
        cameras = [d for d in devices if d.get("model") == G3_MODEL]
        hubs_m3 = [d for d in devices if d.get("model") in M3_MODELS]
        if not cameras and not hubs_m3:
            raise ConfigEntryNotReady("No supported Aqara devices found")

        g3_probe_defs = ALL_BINARY_SENSORS_DEF + ALL_SWITCHES_DEF + ALL_NUMBERS_DEF
        m3_probe_defs = M3_BINARY_SENSORS_DEF + M3_NUMBERS_DEF + M3_SENSORS_DEF + M3_SELECTS_DEF
        supported_devices = cameras + hubs_m3
        dids = [d["did"] for d in supported_devices]

        for device in supported_devices:
            did = device["did"]
            model = device.get("model")
            probe_defs = g3_probe_defs if model == G3_MODEL else m3_probe_defs
            try:
                await api.get_device_states(did, probe_defs)
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
        "hubs_m3": hubs_m3,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
