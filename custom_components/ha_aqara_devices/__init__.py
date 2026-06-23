from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from functools import partial
import logging
from typing import Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType

from .const import (
    A100_PRO_MODELS,
    ACN002_MODELS,
    BRIDGE_SANITY_INTERVAL_SECONDS,
    BRIDGE_UNAVAILABLE_AFTER_FAILURES,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_KEY_ID,
    DOMAIN,
    DEFAULT_BRIDGE_URL,
    FP2_MODEL,
    FP300_MODEL,
    G2H_PRO_MODELS,
    G410_MODELS,
    G4_MODELS,
    G3_MODELS,
    M100_MODELS,
    M3_MODELS,
    PLATFORMS,
    PRESENCE_MODELS,
    TOKEN_REFRESH_STARTUP_MARGIN_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

BRIDGE_START_RETRY_INITIAL_SECONDS = 5
BRIDGE_START_RETRY_MAX_SECONDS = 30

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


def _build_resilient_update(
    fetch_method: Callable[[], Awaitable[dict[str, Any]]],
    did: str,
    label: str,
    unavailable_after_failures: int,
) -> Callable[[], Awaitable[dict[str, Any]]]:
    from .api import AqaraAuthError

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
                    "Aqara %s update failed for %s (%s/%s), keeping last known state: %s",
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


async def _async_refresh_coordinators_after_setup(
    label: str,
    coordinators: list[DataUpdateCoordinator],
    delay_seconds: int = 5,
) -> None:
    """Refresh coordinators once after entities have subscribed to updates."""
    if not coordinators:
        return

    await asyncio.sleep(delay_seconds)
    for coordinator in coordinators:
        try:
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.debug(
                "Delayed Aqara %s refresh failed for %s: %s",
                label,
                coordinator.name,
                err,
            )


def _setup_device_state_coordinators(
    hass: HomeAssistant,
    api,
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
    api,
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


def _enabled_unique_ids_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    entity_registry = er.async_get(hass)
    return {
        str(registry_entry.unique_id)
        for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if registry_entry.unique_id and registry_entry.disabled_by is None
    }


async def _async_start_bridge_with_retry(entry: ConfigEntry, bridge_manager) -> None:
    from .api import AqaraAuthError

    delay = BRIDGE_START_RETRY_INITIAL_SECONDS
    attempt = 1
    while True:
        try:
            _LOGGER.info("Aqara bridge startup attempt %s for %s", attempt, entry.title)
            await bridge_manager.async_start()
        except asyncio.CancelledError:
            raise
        except AqaraAuthError as err:
            _LOGGER.error("Aqara bridge startup stopped because authentication failed: %s", err)
            return
        except Exception as err:
            await bridge_manager.async_stop()
            _LOGGER.warning(
                "Aqara bridge is not ready for %s; retrying in %s seconds: %s",
                entry.title,
                delay,
                err,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, BRIDGE_START_RETRY_MAX_SECONDS)
            attempt += 1
            continue

        _LOGGER.info("Aqara bridge started for %s", entry.title)
        return


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    from .api import AqaraApi, AqaraAuthError
    from .bridge_specs import (
        A100_PRO_STATE_SPECS,
        ACN002_STATE_SPECS,
        G2H_PRO_STATE_SPECS,
        G410_STATE_SPECS,
        G4_STATE_SPECS,
        G3_STATE_SPECS,
        M100_STATE_SPECS,
        M3_STATE_SPECS,
        build_active_subscriptions,
    )
    from .push import AqaraBridgePushManager

    session = aiohttp_client.async_get_clientsession(hass)
    api = AqaraApi(
        entry.data["area"],
        session,
        app_id=entry.data.get(CONF_APP_ID, ""),
        app_key=entry.data.get(CONF_APP_KEY, ""),
        key_id=entry.data.get(CONF_KEY_ID, ""),
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        open_id=entry.data.get("open_id"),
        expires_at=entry.data.get("expires_at"),
    )

    try:
        if not entry.data.get(CONF_APP_ID) or not entry.data.get(CONF_APP_KEY) or not entry.data.get(CONF_KEY_ID):
            raise ConfigEntryAuthFailed(
                "Aqara developer credentials are missing. Reconfigure the integration with app_id, app_key, and key_id."
            )
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
        g2h_pro_cameras = [device for device in devices if device.get("model") in G2H_PRO_MODELS]
        g410_doorbells = [device for device in devices if device.get("model") in G410_MODELS]
        g4_doorbells = [device for device in devices if device.get("model") in G4_MODELS]
        hubs_m3 = [device for device in devices if device.get("model") in M3_MODELS]
        hubs_m100 = [device for device in devices if device.get("model") in M100_MODELS]
        a100_pro_locks = [device for device in devices if device.get("model") in A100_PRO_MODELS]
        acn002_locks = [device for device in devices if device.get("model") in ACN002_MODELS]
        presence_devices = [device for device in devices if device.get("model") in PRESENCE_MODELS]

        if (
            not cameras
            and not g2h_pro_cameras
            and not g410_doorbells
            and not g4_doorbells
            and not hubs_m3
            and not hubs_m100
            and not a100_pro_locks
            and not acn002_locks
            and not presence_devices
        ):
            raise ConfigEntryNotReady(
                "No Aqara G2H Pro, G3, G410, G4, M3, M100, A100 Pro, ACN002, FP2, or FP300 devices found"
            )

    except (ConfigEntryAuthFailed, AqaraAuthError) as err:
        if isinstance(err, AqaraAuthError):
            raise ConfigEntryAuthFailed(str(err)) from err
        raise
    except ConfigEntryNotReady:
        raise
    except Exception as e:
        raise ConfigEntryNotReady(f"Aqara setup not ready: {e}") from e

    camera_coordinators = _setup_device_state_coordinators(hass, api, cameras, "camera-state", G3_STATE_SPECS)
    g2h_pro_coordinators = _setup_device_state_coordinators(
        hass,
        api,
        g2h_pro_cameras,
        "g2h-pro-state",
        G2H_PRO_STATE_SPECS,
    )
    g410_coordinators = _setup_device_state_coordinators(
        hass,
        api,
        g410_doorbells,
        "g410-state",
        G410_STATE_SPECS,
    )
    g4_coordinators = _setup_device_state_coordinators(
        hass,
        api,
        g4_doorbells,
        "g4-state",
        G4_STATE_SPECS,
    )
    m3_coordinators = _setup_device_state_coordinators(hass, api, hubs_m3, "hub-m3-state", M3_STATE_SPECS)
    m100_coordinators = _setup_device_state_coordinators(hass, api, hubs_m100, "hub-m100-state", M100_STATE_SPECS)
    a100_pro_coordinators = _setup_device_state_coordinators(
        hass,
        api,
        a100_pro_locks,
        "a100-pro-state",
        A100_PRO_STATE_SPECS,
    )
    acn002_coordinators = _setup_device_state_coordinators(
        hass,
        api,
        acn002_locks,
        "acn002-state",
        ACN002_STATE_SPECS,
    )
    presence_coordinators = _setup_presence_coordinators(hass, api, presence_devices)

    bridge_url = _entry_bridge_value(entry, CONF_BRIDGE_URL, DEFAULT_BRIDGE_URL)
    bridge_token = _entry_bridge_value(entry, CONF_BRIDGE_TOKEN)
    if not bridge_url or not bridge_token:
        raise ConfigEntryNotReady("Aqara bridge configuration missing. Update the integration options.")

    entry_data = {
        "api": api,
        "cameras": cameras,
        "g2h_pro_cameras": g2h_pro_cameras,
        "g410_doorbells": g410_doorbells,
        "g4_doorbells": g4_doorbells,
        "hubs_m3": hubs_m3,
        "hubs_m100": hubs_m100,
        "a100_pro_locks": a100_pro_locks,
        "acn002_locks": acn002_locks,
        "presence_devices": presence_devices,
        "camera_coordinators": camera_coordinators,
        "g2h_pro_coordinators": g2h_pro_coordinators,
        "g410_coordinators": g410_coordinators,
        "g4_coordinators": g4_coordinators,
        "m3_coordinators": m3_coordinators,
        "m100_coordinators": m100_coordinators,
        "a100_pro_coordinators": a100_pro_coordinators,
        "acn002_coordinators": acn002_coordinators,
        "presence_coordinators": presence_coordinators,
        "bridge_manager": None,
        "bridge_task": None,
        "warmup_tasks": [],
        "active_subscriptions": [],
    }
    hass.data[DOMAIN][entry.entry_id] = entry_data

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    enabled_unique_ids = _enabled_unique_ids_for_entry(hass, entry)
    active_subscriptions = build_active_subscriptions(
        enabled_unique_ids,
        cameras,
        g2h_pro_cameras,
        g410_doorbells,
        g4_doorbells,
        hubs_m3,
        hubs_m100,
        a100_pro_locks,
        acn002_locks,
        presence_devices,
    )
    entry_data["active_subscriptions"] = active_subscriptions

    bridge_manager = AqaraBridgePushManager(
        hass,
        session,
        api,
        bridge_url,
        bridge_token,
        cameras,
        g2h_pro_cameras,
        g410_doorbells,
        g4_doorbells,
        hubs_m3,
        hubs_m100,
        a100_pro_locks,
        acn002_locks,
        presence_devices,
        camera_coordinators,
        g2h_pro_coordinators,
        g410_coordinators,
        g4_coordinators,
        m3_coordinators,
        m100_coordinators,
        a100_pro_coordinators,
        acn002_coordinators,
        presence_coordinators,
        active_subscriptions,
    )

    entry_data["bridge_manager"] = bridge_manager
    entry_data["bridge_task"] = hass.async_create_background_task(
        _async_start_bridge_with_retry(entry, bridge_manager),
        f"{DOMAIN} bridge startup",
    )
    if acn002_coordinators:
        entry_data["warmup_tasks"].append(
            hass.async_create_background_task(
                _async_refresh_coordinators_after_setup(
                    "acn002-state",
                    list(acn002_coordinators.values()),
                ),
                f"{DOMAIN} ACN002 delayed refresh",
            )
        )

    total_resources = sum(len(subscription["resourceIds"]) for subscription in active_subscriptions)
    _LOGGER.info(
        "Aqara bridge subscriptions built for %s device(s), %s active resource(s)",
        len(active_subscriptions),
        total_resources,
    )

    @callback
    def _handle_entity_registry_update(event) -> None:
        if event.data.get("action") != "update":
            return

        changes = event.data.get("changes") or {}
        if "disabled_by" not in changes:
            return

        entity_id = event.data.get("entity_id")
        if not entity_id:
            return

        registry_entry = er.async_get(hass).async_get(entity_id)
        if registry_entry is None or registry_entry.config_entry_id != entry.entry_id:
            return

        change_label = "enabled" if changes["disabled_by"] is None else "disabled"
        _LOGGER.info("Aqara entity %s was %s; scheduling integration reload", entity_id, change_label)
        hass.config_entries.async_schedule_reload(entry.entry_id)

    entry.async_on_unload(hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _handle_entity_registry_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id)
    bridge_task = None if entry_data is None else entry_data.get("bridge_task")
    if bridge_task is not None:
        bridge_task.cancel()
        with suppress(asyncio.CancelledError):
            await bridge_task
    warmup_tasks = [] if entry_data is None else entry_data.get("warmup_tasks", [])
    for task in warmup_tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    bridge_manager = None if entry_data is None else entry_data.get("bridge_manager")
    if bridge_manager is not None:
        await bridge_manager.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data.pop(entry.entry_id, None)
    return unload_ok
