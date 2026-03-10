from __future__ import annotations

from datetime import timedelta
from functools import partial
from importlib import import_module
import logging
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType

from .api import AqaraApi
from .const import (
    DOMAIN,
    FP2_FAST_INTERVAL_SECONDS,
    FP2_FAST_UNAVAILABLE_AFTER_FAILURES,
    FP2_MODEL,
    FP2_PRESENCE_INTERVAL_SECONDS,
    FP2_PRESENCE_UNAVAILABLE_AFTER_FAILURES,
    FP300_FAST_INTERVAL_SECONDS,
    FP300_FAST_UNAVAILABLE_AFTER_FAILURES,
    FP300_MODEL,
    G3_MODELS,
    M3_MODELS,
    PLATFORMS,
    PRESENCE_MEDIUM_INTERVAL_SECONDS,
    PRESENCE_MODELS,
    PRESENCE_SLOW_INTERVAL_SECONDS,
    PRESENCE_UNAVAILABLE_AFTER_FAILURES,
)

# Preload platform modules so Home Assistant doesn't import them inside the event loop
for _platform in PLATFORMS:
    import_module(f".{_platform}", __package__)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


def _build_resilient_presence_update(
    fetch_method: Callable[[], Awaitable[dict[str, Any]]],
    did: str,
    label: str,
    unavailable_after_failures: int,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    state: dict[str, Any] = {"failures": 0, "last_data": None}

    async def _async_update() -> dict[str, Any]:
        try:
            data = await fetch_method()
        except Exception as err:
            state["failures"] += 1
            if state["last_data"] is not None and state["failures"] < unavailable_after_failures:
                _LOGGER.warning(
                    "Presence %s update failed for %s (%s/%s), keeping last known state: %s",
                    label,
                    did,
                    state["failures"],
                    unavailable_after_failures,
                    err,
                )
                return state["last_data"]
            raise UpdateFailed(str(err)) from err

        state["last_data"] = data
        state["failures"] = 0
        return data

    return _async_update


def _create_presence_coordinator(
    hass: HomeAssistant,
    did: str,
    label: str,
    fetch_method: Callable[[], Awaitable[dict[str, Any]]],
    interval_seconds: int,
    unavailable_after_failures: int,
) -> DataUpdateCoordinator:
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}-presence-{label}-{did}",
        update_method=_build_resilient_presence_update(
            fetch_method,
            did,
            label,
            unavailable_after_failures,
        ),
        update_interval=timedelta(seconds=interval_seconds),
    )
    hass.async_create_task(coordinator.async_refresh())
    return coordinator


def _setup_presence_coordinators(
    hass: HomeAssistant,
    api: AqaraApi,
    presence_devices: list[dict[str, Any]],
) -> dict[str, dict[str, DataUpdateCoordinator]]:
    coordinators: dict[str, dict[str, DataUpdateCoordinator]] = {}

    for presence in presence_devices:
        did = presence["did"]
        model = str(presence.get("model") or "")
        if model == FP2_MODEL:
            device_coordinators = {
                "fast": _create_presence_coordinator(
                    hass,
                    did,
                    "fast",
                    partial(api.get_presence_fast_state, did, model),
                    FP2_FAST_INTERVAL_SECONDS,
                    FP2_FAST_UNAVAILABLE_AFTER_FAILURES,
                ),
                "presence": _create_presence_coordinator(
                    hass,
                    did,
                    "presence",
                    partial(api.get_fp2_presence, did),
                    FP2_PRESENCE_INTERVAL_SECONDS,
                    FP2_PRESENCE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "medium": _create_presence_coordinator(
                    hass,
                    did,
                    "medium",
                    partial(api.get_presence_medium_state, did, model),
                    PRESENCE_MEDIUM_INTERVAL_SECONDS,
                    PRESENCE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "slow": _create_presence_coordinator(
                    hass,
                    did,
                    "slow",
                    partial(api.get_presence_slow_state, did, model),
                    PRESENCE_SLOW_INTERVAL_SECONDS,
                    PRESENCE_UNAVAILABLE_AFTER_FAILURES,
                ),
            }
        elif model == FP300_MODEL:
            device_coordinators = {
                "fast": _create_presence_coordinator(
                    hass,
                    did,
                    "fast",
                    partial(api.get_presence_fast_state, did, model),
                    FP300_FAST_INTERVAL_SECONDS,
                    FP300_FAST_UNAVAILABLE_AFTER_FAILURES,
                ),
                "medium": _create_presence_coordinator(
                    hass,
                    did,
                    "medium",
                    partial(api.get_presence_medium_state, did, model),
                    PRESENCE_MEDIUM_INTERVAL_SECONDS,
                    PRESENCE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "slow": _create_presence_coordinator(
                    hass,
                    did,
                    "slow",
                    partial(api.get_presence_slow_state, did, model),
                    PRESENCE_SLOW_INTERVAL_SECONDS,
                    PRESENCE_UNAVAILABLE_AFTER_FAILURES,
                ),
            }
        else:
            continue

        coordinators[did] = device_coordinators

    return coordinators


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(entry.data["area"], session)

    try:
        await api.login(entry.data["username"], entry.data["password"])
        devices = await api.get_devices()

        cameras = [device for device in devices if device.get("model") in G3_MODELS]
        hubs_m3 = [device for device in devices if device.get("model") in M3_MODELS]
        presence_devices = [device for device in devices if device.get("model") in PRESENCE_MODELS]

        if not cameras and not hubs_m3 and not presence_devices:
            raise ConfigEntryNotReady("No Aqara G3, M3, FP2, or FP300 devices found")

    except ConfigEntryNotReady:
        raise
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "cameras": cameras,
        "hubs_m3": hubs_m3,
        "presence_devices": presence_devices,
        "presence_coordinators": _setup_presence_coordinators(hass, api, presence_devices),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
