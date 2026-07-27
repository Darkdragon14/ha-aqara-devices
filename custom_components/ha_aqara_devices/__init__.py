from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from functools import partial
import logging
from typing import Any, Awaitable, Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import aiohttp_client, config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType

from .child_devices import (
    build_child_active_subscriptions,
    build_child_entity_specs,
    child_enabled_resource_ids,
    child_resource_spec_maps,
    child_specs_by_did,
)
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
    M200_MODELS,
    M3_MODELS,
    PLATFORMS,
    PRESENCE_MODELS,
    TOKEN_REFRESH_STARTUP_MARGIN_SECONDS,
    U200_INTERVAL_SECONDS,
    U200_MODELS,
)
from .entity_migration import remove_obsolete_g410_entities

_LOGGER = logging.getLogger(__name__)

BRIDGE_START_RETRY_INITIAL_SECONDS = 5
BRIDGE_START_RETRY_MAX_SECONDS = 30
SERVICE_OPEN_PAIRING_MODE = "open_pairing_mode"
SERVICE_CLOSE_PAIRING_MODE = "close_pairing_mode"
ATTR_DID = "did"
ATTR_DURATION = "duration"
PAIRING_PARENT_DEVICE_KEYS = (
    "cameras",
    "g2h_pro_cameras",
    "hubs_m3",
    "hubs_m100",
    "hubs_m200",
)

PAIRING_OPEN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DID): cv.string,
        vol.Optional(ATTR_DURATION, default=60): vol.All(vol.Coerce(int), vol.Range(min=1, max=600)),
    }
)
PAIRING_CLOSE_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_DID): cv.string})

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def _handle_open_pairing_mode(call: ServiceCall) -> None:
        did = str(call.data[ATTR_DID]).strip()
        duration = int(call.data[ATTR_DURATION])
        api = _api_for_pairing_hub(hass, did)
        response = await api.open_device_connect(did, duration)
        if str(response.get("code")) != "0":
            raise HomeAssistantError(f"Failed to open Aqara pairing mode for {did}: {response}")
        _LOGGER.info("Opened Aqara pairing mode for %s during %s seconds", did, duration)

    async def _handle_close_pairing_mode(call: ServiceCall) -> None:
        did = str(call.data[ATTR_DID]).strip()
        api = _api_for_pairing_hub(hass, did)
        response = await api.close_device_connect(did)
        if str(response.get("code")) != "0":
            raise HomeAssistantError(f"Failed to close Aqara pairing mode for {did}: {response}")
        _LOGGER.info("Closed Aqara pairing mode for %s", did)

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_PAIRING_MODE,
        _handle_open_pairing_mode,
        schema=PAIRING_OPEN_SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLOSE_PAIRING_MODE,
        _handle_close_pairing_mode,
        schema=PAIRING_CLOSE_SERVICE_SCHEMA,
    )
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


def _create_noop_coordinator(hass: HomeAssistant, did: str, label: str) -> DataUpdateCoordinator:
    async def _async_update() -> dict[str, Any]:
        return {}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}-{label}-{did}",
        update_method=_async_update,
        update_interval=None,
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


def _setup_u200_coordinators(
    hass: HomeAssistant,
    api,
    u200_locks: list[dict[str, Any]],
) -> dict[str, DataUpdateCoordinator]:
    coordinators: dict[str, DataUpdateCoordinator] = {}
    for lock in u200_locks:
        did = lock["did"]
        coordinators[did] = _create_resilient_coordinator(
            hass,
            did,
            "u200-lock-state",
            partial(api.get_u200_state, did),
            U200_INTERVAL_SECONDS,
            BRIDGE_UNAVAILABLE_AFTER_FAILURES,
        )
    return coordinators


def _setup_child_coordinators(
    hass: HomeAssistant,
    api,
    child_entity_specs: list[dict[str, Any]],
    enabled_unique_ids: set[str],
    known_unique_ids: set[str],
) -> dict[str, DataUpdateCoordinator]:
    coordinators: dict[str, DataUpdateCoordinator] = {}
    for did, specs in child_specs_by_did(child_entity_specs).items():
        resource_ids = child_enabled_resource_ids(enabled_unique_ids, specs, known_unique_ids=known_unique_ids)
        if not resource_ids:
            coordinators[did] = _create_noop_coordinator(hass, did, "child-state")
            continue
        coordinators[did] = _create_resilient_coordinator(
            hass,
            did,
            "child-state",
            partial(api.get_resource_values, did, resource_ids),
            BRIDGE_SANITY_INTERVAL_SECONDS,
            BRIDGE_UNAVAILABLE_AFTER_FAILURES,
        )
    return coordinators


def _api_for_pairing_hub(hass: HomeAssistant, did: str):
    if not did:
        raise HomeAssistantError("Aqara hub DID is required")

    domain_data = hass.data.get(DOMAIN, {})
    for entry_data in domain_data.values():
        if not isinstance(entry_data, dict):
            continue
        for key in PAIRING_PARENT_DEVICE_KEYS:
            for device in entry_data.get(key, []):
                if str(device.get("did") or "").strip() == did:
                    return entry_data["api"]

    raise HomeAssistantError(
        f"Aqara hub DID {did} was not found among loaded pairing-capable hubs"
    )


def _entry_bridge_value(entry: ConfigEntry, key: str, default: str = "") -> str:
    return str(entry.options.get(key) or entry.data.get(key) or default).strip()


def _has_aqara_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _first_aqara_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if _has_aqara_value(value):
            return value
    return None


def _flatten_aqara_items(data: Any) -> list[dict[str, Any]]:
    raw_result = data.get("result", []) if isinstance(data, dict) else data
    if isinstance(raw_result, list):
        return [item for item in raw_result if isinstance(item, dict)]
    if isinstance(raw_result, dict):
        for key in ("data", "items", "list", "devices", "result"):
            maybe = raw_result.get(key)
            if isinstance(maybe, list):
                return [item for item in maybe if isinstance(item, dict)]
        if raw_result:
            return [raw_result]
    return []


def _normalize_child_device(raw: dict[str, Any], fallback_parent_did: str | None = None) -> dict[str, Any] | None:
    did = str(_first_aqara_value(raw, ("did", "deviceId", "subjectId")) or "").strip()
    parent_did = str(_first_aqara_value(raw, ("parentDid", "parentDeviceId", "gatewayDid")) or fallback_parent_did or "").strip()
    model = str(_first_aqara_value(raw, ("model", "modelId", "modelID", "deviceModel", "modelName")) or "").strip()
    if not did or not parent_did:
        _LOGGER.debug(
            "Ignoring Aqara child device with missing identifiers: did=%s parentDid=%s raw=%s",
            did,
            parent_did,
            raw,
        )
        return None
    if did == parent_did:
        _LOGGER.debug("Ignoring Aqara child device with matching did and parentDid: %s", raw)
        return None

    device_name = str(
        _first_aqara_value(raw, ("deviceName", "name", "nickName", "nickname", "displayName")) or model or did
    ).strip()
    normalized = {
        "did": did,
        "parentDid": parent_did,
        "modelType": raw.get("modelType"),
        "state": raw.get("state"),
        "model": model,
        "deviceName": device_name,
        "firmwareVersion": raw.get("firmwareVersion"),
        "positionId": raw.get("positionId"),
    }
    for key, value in raw.items():
        normalized.setdefault(key, value)
    return normalized


def _merge_child_device(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if existing is None:
        return new
    merged = dict(existing)
    for key, value in new.items():
        if key in {"did", "parentDid", "model"}:
            if not _has_aqara_value(merged.get(key)) and _has_aqara_value(value):
                merged[key] = value
            continue
        if _has_aqara_value(value) or not _has_aqara_value(merged.get(key)):
            merged[key] = value
    return merged


async def _discover_child_devices(api, parent_devices: list[dict[str, Any]], all_devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    children_by_did: dict[str, dict[str, Any]] = {}
    parent_dids = {str(device.get("did") or "").strip() for device in parent_devices if device.get("did")}

    for device in all_devices:
        parent_did = str(device.get("parentDid") or "").strip()
        if not parent_did or parent_did not in parent_dids:
            continue
        child = _normalize_child_device(device)
        if child is not None:
            children_by_did[child["did"]] = _merge_child_device(children_by_did.get(child["did"]), child)

    for parent in parent_devices:
        parent_did = str(parent.get("did") or "").strip()
        if not parent_did:
            continue
        try:
            data = await api.query_device_sub_info(parent_did)
        except Exception as err:
            _LOGGER.debug("Failed to query Aqara child devices for parent %s: %s", parent_did, err)
            continue
        if str(data.get("code")) != "0":
            _LOGGER.debug("Aqara child device query failed for parent %s: %s", parent_did, data)
            continue
        _LOGGER.debug("Aqara child device payload for parent %s: %s", parent_did, data.get("result"))
        for raw_child in _flatten_aqara_items(data):
            child = _normalize_child_device(raw_child, parent_did)
            if child is not None:
                children_by_did[child["did"]] = _merge_child_device(children_by_did.get(child["did"]), child)

    return list(children_by_did.values())


async def _query_child_resource_info(api, child_devices: list[dict[str, Any]]) -> dict[str, Any]:
    resource_info: dict[str, Any] = {}
    models = sorted({str(device.get("model") or "").strip() for device in child_devices if device.get("model")})
    for model in models:
        try:
            data = await api.query_resource_info(model)
        except Exception as err:
            _LOGGER.debug("Failed to query Aqara child resource info for model %s: %s", model, err)
            continue
        if str(data.get("code")) != "0":
            _LOGGER.debug("Aqara child resource info query failed for model %s: %s", model, data)
            continue
        resource_info[model] = data.get("result")
        _LOGGER.debug("Aqara child resource info for model %s: %s", model, data.get("result"))
    return resource_info


def _group_child_devices_by_parent(child_devices: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for child in child_devices:
        grouped.setdefault(str(child["parentDid"]), []).append(child)
    return grouped


def _register_child_devices(hass: HomeAssistant, entry: ConfigEntry, child_devices: list[dict[str, Any]]) -> None:
    device_registry = dr.async_get(hass)
    for child in child_devices:
        did = str(child.get("did") or "").strip()
        parent_did = str(child.get("parentDid") or "").strip()
        if not did or not parent_did:
            _LOGGER.debug("Skipping Aqara child registry entry with missing did or parentDid: %s", child)
            continue

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, did)},
            manufacturer="Aqara",
            name=str(child.get("deviceName") or did),
            model=str(child.get("model") or "Aqara child device"),
            model_id=str(child.get("model") or did),
            sw_version=None if child.get("firmwareVersion") is None else str(child.get("firmwareVersion")),
            via_device=(DOMAIN, parent_did),
        )
        _LOGGER.debug(
            "Registered Aqara child device: did=%s parentDid=%s model=%s name=%s",
            did,
            parent_did,
            child.get("model"),
            child.get("deviceName"),
        )


def _enabled_unique_ids_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    entity_registry = er.async_get(hass)
    return {
        str(registry_entry.unique_id)
        for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if registry_entry.unique_id and registry_entry.disabled_by is None
    }


def _known_unique_ids_for_entry(hass: HomeAssistant, entry: ConfigEntry) -> set[str]:
    entity_registry = er.async_get(hass)
    return {
        str(registry_entry.unique_id)
        for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if registry_entry.unique_id
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
        M200_STATE_SPECS,
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
        hubs_m200 = [device for device in devices if device.get("model") in M200_MODELS]
        a100_pro_locks = [device for device in devices if device.get("model") in A100_PRO_MODELS]
        acn002_locks = [device for device in devices if device.get("model") in ACN002_MODELS]
        presence_devices = [device for device in devices if device.get("model") in PRESENCE_MODELS]
        u200_locks = [device for device in devices if device.get("model") in U200_MODELS]
        remove_obsolete_g410_entities(hass, entry.entry_id, g410_doorbells)

        hub_parent_devices = [
            *cameras,
            *g2h_pro_cameras,
            *hubs_m3,
            *hubs_m100,
            *hubs_m200,
        ]
        child_devices = await _discover_child_devices(api, hub_parent_devices, devices)
        child_devices_by_parent = _group_child_devices_by_parent(child_devices)
        child_resource_info = await _query_child_resource_info(api, child_devices)
        supported_dids = {
            str(device.get("did") or "")
            for device in (
                cameras
                + g2h_pro_cameras
                + g410_doorbells
                + g4_doorbells
                + hubs_m3
                + hubs_m100
                + hubs_m200
                + a100_pro_locks
                + acn002_locks
                + presence_devices
                + u200_locks
            )
            if device.get("did")
        }
        child_entity_specs = build_child_entity_specs(child_devices, child_resource_info, supported_dids)
        child_resource_specs = child_resource_spec_maps(child_entity_specs)

        if (
            not cameras
            and not g2h_pro_cameras
            and not g410_doorbells
            and not g4_doorbells
            and not hubs_m3
            and not hubs_m100
            and not hubs_m200
            and not a100_pro_locks
            and not acn002_locks
            and not presence_devices
            and not u200_locks
        ):
            raise ConfigEntryNotReady(
                "No Aqara G2H Pro, G3, G410, G4, M3, M100, M200, A100, A100 Pro, ACN002, FP2, FP300, or U200 devices found"
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
    m200_coordinators = _setup_device_state_coordinators(hass, api, hubs_m200, "hub-m200-state", M200_STATE_SPECS)
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
    u200_coordinators = _setup_u200_coordinators(hass, api, u200_locks)
    enabled_unique_ids = _enabled_unique_ids_for_entry(hass, entry)
    known_unique_ids = _known_unique_ids_for_entry(hass, entry)
    child_coordinators = _setup_child_coordinators(
        hass,
        api,
        child_entity_specs,
        enabled_unique_ids,
        known_unique_ids,
    )

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
        "hubs_m200": hubs_m200,
        "a100_pro_locks": a100_pro_locks,
        "acn002_locks": acn002_locks,
        "presence_devices": presence_devices,
        "u200_locks": u200_locks,
        "child_devices": child_devices,
        "child_devices_by_parent": child_devices_by_parent,
        "child_resource_info": child_resource_info,
        "child_entity_specs": child_entity_specs,
        "child_resource_specs": child_resource_specs,
        "child_coordinators": child_coordinators,
        "camera_coordinators": camera_coordinators,
        "g2h_pro_coordinators": g2h_pro_coordinators,
        "g410_coordinators": g410_coordinators,
        "g4_coordinators": g4_coordinators,
        "m3_coordinators": m3_coordinators,
        "m100_coordinators": m100_coordinators,
        "m200_coordinators": m200_coordinators,
        "a100_pro_coordinators": a100_pro_coordinators,
        "acn002_coordinators": acn002_coordinators,
        "presence_coordinators": presence_coordinators,
        "u200_coordinators": u200_coordinators,
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

    _register_child_devices(hass, entry, child_devices)

    enabled_unique_ids = _enabled_unique_ids_for_entry(hass, entry)
    active_subscriptions = build_active_subscriptions(
        enabled_unique_ids,
        cameras,
        g2h_pro_cameras,
        g410_doorbells,
        g4_doorbells,
        hubs_m3,
        hubs_m100,
        hubs_m200,
        a100_pro_locks,
        acn002_locks,
        presence_devices,
    )
    active_subscriptions.extend(build_child_active_subscriptions(enabled_unique_ids, child_entity_specs))
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
        hubs_m200,
        a100_pro_locks,
        acn002_locks,
        presence_devices,
        child_devices,
        camera_coordinators,
        g2h_pro_coordinators,
        g410_coordinators,
        g4_coordinators,
        m3_coordinators,
        m100_coordinators,
        m200_coordinators,
        a100_pro_coordinators,
        acn002_coordinators,
        presence_coordinators,
        child_coordinators,
        child_resource_specs,
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
