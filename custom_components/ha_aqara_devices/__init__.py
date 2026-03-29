from __future__ import annotations

from datetime import timedelta
from functools import partial
from importlib import import_module
import logging
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType

from .api import AqaraApi, AqaraAuthError
from .bridge_specs import G3_STATE_SPECS, M3_STATE_SPECS
from .const import (
    BRIDGE_SANITY_INTERVAL_SECONDS,
    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    DOMAIN,
    DEFAULT_BRIDGE_URL,
    FP2_MODEL,
    FP300_MODEL,
    G3_MODELS,
    M3_MODELS,
    PLATFORMS,
    PRESENCE_MODELS,
    TOKEN_REFRESH_STARTUP_MARGIN_SECONDS,
)
from .push import AqaraBridgePushManager

# Preload platform modules so Home Assistant doesn't import them inside the event loop
for _platform in PLATFORMS:
    import_module(f".{_platform}", __package__)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


def _build_resilient_update(
    fetch_method: Callable[[], Awaitable[dict[str, Any]]],
    did: str,
    label: str,
    unavailable_after_failures: int,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    state: dict[str, Any] = {"failures": 0, "last_data": None}

    async def _async_update() -> dict[str, Any]:
        try:
            data = await fetch_method()
        except AqaraAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
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


def _create_resilient_coordinator(
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
        name=f"{DOMAIN}-{label}-{did}",
        update_method=_build_resilient_update(
            fetch_method,
            did,
            label,
            unavailable_after_failures,
        ),
        update_interval=timedelta(seconds=interval_seconds),
    )
    hass.async_create_task(coordinator.async_refresh())
    return coordinator


def _setup_device_state_coordinators(
    hass: HomeAssistant,
    api: AqaraApi,
    devices: list[dict[str, Any]],
    label: str,
    state_defs: list[dict[str, Any]],
) -> dict[str, DataUpdateCoordinator]:
    coordinators: dict[str, DataUpdateCoordinator] = {}
    for device in devices:
        did = device["did"]
        coordinators[did] = _create_resilient_coordinator(
            hass,
            did,
            label,
            partial(api.get_device_states, did, state_defs),
            BRIDGE_SANITY_INTERVAL_SECONDS,
            BRIDGE_UNAVAILABLE_AFTER_FAILURES,
        )
    return coordinators


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
                "fast": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-fast",
                    partial(api.get_presence_fast_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "presence": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-presence",
                    partial(api.get_fp2_presence, did),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "medium": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-medium",
                    partial(api.get_presence_medium_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "slow": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-slow",
                    partial(api.get_presence_slow_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
            }
        elif model == FP300_MODEL:
            device_coordinators = {
                "fast": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-fast",
                    partial(api.get_presence_fast_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "medium": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-medium",
                    partial(api.get_presence_medium_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
                "slow": _create_resilient_coordinator(
                    hass,
                    did,
                    "presence-slow",
                    partial(api.get_presence_slow_state, did, model),
                    BRIDGE_SANITY_INTERVAL_SECONDS,
                    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
                ),
            }
        else:
            continue

        coordinators[did] = device_coordinators

    return coordinators


def _entry_bridge_value(entry: ConfigEntry, key: str, default: str = "") -> str:
    return str(entry.options.get(key) or entry.data.get(key) or default).strip()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(
        entry.data["area"],
        session,
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        open_id=entry.data.get("open_id"),
        expires_at=entry.data.get("expires_at"),
    )

    try:
        if not entry.data.get("access_token") or not entry.data.get("refresh_token"):
            raise ConfigEntryAuthFailed(
                "Aqara Open API tokens missing. Reconfigure the integration with the new authorization-code flow."
            )
        await api.ensure_valid_access_token(TOKEN_REFRESH_STARTUP_MARGIN_SECONDS)
        if api.export_auth() != {
            "access_token": entry.data.get("access_token"),
            "refresh_token": entry.data.get("refresh_token"),
            "open_id": entry.data.get("open_id"),
            "expires_at": entry.data.get("expires_at"),
        }:
            hass.config_entries.async_update_entry(entry, data={**entry.data, **api.export_auth()})
        devices = await api.get_devices()

        cameras = [device for device in devices if device.get("model") in G3_MODELS]
        hubs_m3 = [device for device in devices if device.get("model") in M3_MODELS]
        presence_devices = [device for device in devices if device.get("model") in PRESENCE_MODELS]

        if not cameras and not hubs_m3 and not presence_devices:
            raise ConfigEntryNotReady("No Aqara G3, M3, FP2, or FP300 devices found")

    except (ConfigEntryAuthFailed, AqaraAuthError) as err:
        if isinstance(err, AqaraAuthError):
            raise ConfigEntryAuthFailed(str(err)) from err
        raise
    except ConfigEntryNotReady:
        raise
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    camera_coordinators = _setup_device_state_coordinators(hass, api, cameras, "camera-state", G3_STATE_SPECS)
    m3_coordinators = _setup_device_state_coordinators(hass, api, hubs_m3, "hub-m3-state", M3_STATE_SPECS)
    presence_coordinators = _setup_presence_coordinators(hass, api, presence_devices)

    bridge_url = _entry_bridge_value(entry, CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)
    bridge_token = _entry_bridge_value(entry, CONF_BRIDGE_TOKEN)
    if not bridge_url or not bridge_token:
        raise ConfigEntryNotReady("Aqara bridge configuration missing. Update the integration options.")

    bridge_manager = AqaraBridgePushManager(
        hass,
        session,
        api,
        bridge_url,
        bridge_token,
        cameras,
        hubs_m3,
        presence_devices,
        camera_coordinators,
        m3_coordinators,
        presence_coordinators,
    )

    try:
        await bridge_manager.async_start()
    except AqaraAuthError as e:
        raise ConfigEntryAuthFailed(str(e)) from e
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara bridge setup not ready: {e}") from e

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "cameras": cameras,
        "hubs_m3": hubs_m3,
        "presence_devices": presence_devices,
        "camera_coordinators": camera_coordinators,
        "m3_coordinators": m3_coordinators,
        "presence_coordinators": presence_coordinators,
        "bridge_manager": bridge_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry_data = hass.data[DOMAIN].get(entry.entry_id)
    bridge_manager = None if entry_data is None else entry_data.get("bridge_manager")
    if bridge_manager is not None:
        await bridge_manager.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
