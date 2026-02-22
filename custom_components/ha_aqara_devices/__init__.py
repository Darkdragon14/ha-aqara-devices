from __future__ import annotations

from importlib import import_module
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import AqaraApi
from .binary_sensors import ALL_BINARY_SENSORS_DEF, M3_BINARY_SENSORS_DEF
from .const import DOMAIN, FP2_MODEL, G3_MODELS, M3_MODELS, PLATFORMS
from .numbers import ALL_NUMBERS_DEF, M3_NUMBERS_DEF
from .selects import M3_SELECTS_DEF
from .sensors import M3_SENSORS_DEF
from .switches import ALL_SWITCHES_DEF

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

        cameras = [device for device in devices if device.get("model") in G3_MODELS]
        hubs_m3 = [device for device in devices if device.get("model") in M3_MODELS]
        fp2_devices = [device for device in devices if device.get("model") == FP2_MODEL]

        if not cameras and not hubs_m3 and not fp2_devices:
            raise ConfigEntryNotReady("No Aqara G3, M3, or FP2 devices found")

        g3_probe_defs = ALL_BINARY_SENSORS_DEF + ALL_SWITCHES_DEF + ALL_NUMBERS_DEF
        m3_probe_defs = M3_BINARY_SENSORS_DEF + M3_NUMBERS_DEF + M3_SENSORS_DEF + M3_SELECTS_DEF

        for cam in cameras:
            did = cam["did"]
            try:
                await api.get_device_states(did, g3_probe_defs)
            except Exception as e:
                raise ConfigEntryNotReady(f"G3 probe failed for {did}: {e}") from e

        for hub in hubs_m3:
            did = hub["did"]
            try:
                await api.get_device_states(did, m3_probe_defs)
            except Exception as e:
                raise ConfigEntryNotReady(f"M3 probe failed for {did}: {e}") from e

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
        "hubs_m3": hubs_m3,
        "fp2_devices": fp2_devices,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
