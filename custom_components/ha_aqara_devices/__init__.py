from __future__ import annotations

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
    G3_MODELS,
    M3_MODELS,
    PLATFORMS,
    PRESENCE_MODELS,
    TOKEN_REFRESH_STARTUP_MARGIN_SECONDS,
)

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    from .api import AqaraApi, AqaraAuthError
    from .bridge_specs import G3_STATE_SPECS, M3_STATE_SPECS, build_active_subscriptions
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

    entry_data = {
        "api": api,
        "cameras": cameras,
        "hubs_m3": hubs_m3,
        "presence_devices": presence_devices,
        "camera_coordinators": camera_coordinators,
        "m3_coordinators": m3_coordinators,
        "presence_coordinators": presence_coordinators,
        "bridge_manager": None,
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
    active_subscriptions = build_active_subscriptions(enabled_unique_ids, cameras, hubs_m3, presence_devices)
    entry_data["active_subscriptions"] = active_subscriptions

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
        active_subscriptions,
    )

    try:
        await bridge_manager.async_start()
    except AqaraAuthError as e:
        await bridge_manager.async_stop()
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryAuthFailed(str(e)) from e
    except Exception as e:
        await bridge_manager.async_stop()
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(f"Aqara bridge setup not ready: {e}") from e

    entry_data["bridge_manager"] = bridge_manager

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
    bridge_manager = None if entry_data is None else entry_data.get("bridge_manager")
    if bridge_manager is not None:
        await bridge_manager.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        domain_data.pop(entry.entry_id, None)
    return unload_ok
