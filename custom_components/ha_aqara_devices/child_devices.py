from __future__ import annotations

import logging
import re
from typing import Any, Iterable

_LOGGER = logging.getLogger(__name__)

CHILD_SENSOR_PLATFORM = "sensor"
CHILD_BINARY_SENSOR_PLATFORM = "binary_sensor"
CHILD_SUBSCRIPTION_ATTACH = "ha_aqara_devices"
AQARA_ACCESS_FLAGS = {
    1: (True, False, False),
    2: (False, False, True),
    3: (True, False, True),
    4: (False, True, False),
    5: (True, True, False),
    6: (False, True, True),
    7: (True, True, True),
}
SAFE_DEFAULT_NAME_MARKERS = {
    "battery",
    "temperature",
    "humidity",
    "illuminance",
    "illumination",
    "light",
    "lux",
    "voltage",
    "signal",
    "rssi",
    "motion",
    "occupancy",
    "presence",
    "contact",
    "door",
    "window",
    "leak",
    "smoke",
    "gas",
    "co2",
    "pm2",
    "pm10",
}
SMOKE_SENSOR_MODEL = "lumi.sensor_smoke.acn03"
SMOKE_SENSOR_TRANSLATION_KEYS_BY_RESOURCE_ID = {
    "4.12.85": "smoke_manual_mute",
    "4.15.85": "smoke_self_test",
    "8.0.2007": "zigbee_signal_strength",
    "8.0.2008": "battery_voltage",
    "8.0.2232": "smoke_alarm",
    "8.0.2234": "smoke_fault_alarm",
    "8.0.9001": "low_battery_alarm",
}
SMOKE_SENSOR_TRANSLATION_KEYS_BY_NAME = {
    "heartbeat indicator light": "heartbeat_indicator",
    "zigbee信号强度": "zigbee_signal_strength",
    "低电压报警": "low_battery_alarm",
    "故障报警": "smoke_fault_alarm",
    "消音": "smoke_manual_mute",
    "电池电压值": "battery_voltage",
    "自检": "smoke_self_test",
    "设备报警": "smoke_alarm",
}


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _first_value(data: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if _has_value(value):
            return value
    return None


def child_unique_id(did: str, resource_id: str) -> str:
    return f"{did}_child_{resource_id}"


def _flatten_resource_info(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ("resources", "data", "items", "list", "attributes", "properties", "resourceInfos", "resourceInfo"):
        maybe = data.get(key)
        if isinstance(maybe, list):
            return [item for item in maybe if isinstance(item, dict)]

    mapped_items: list[dict[str, Any]] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        item = dict(value)
        item.setdefault("resourceId", key)
        mapped_items.append(item)
    if mapped_items:
        return mapped_items

    return [data] if data.get("resourceId") else []


def _truthy_access(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return bool(value)


def _access_flags(resource: dict[str, Any]) -> tuple[bool, bool, bool]:
    access = resource.get("access")
    if access is None:
        access = resource.get("permission") or resource.get("permissions") or resource.get("accessMode")

    if isinstance(access, dict):
        readable = any(_truthy_access(access.get(key)) for key in ("read", "readable", "query", "queryable"))
        writable = any(_truthy_access(access.get(key)) for key in ("write", "writable", "set", "settable"))
        reportable = any(_truthy_access(access.get(key)) for key in ("report", "reportable", "notify", "notifiable"))
        return readable, writable, reportable

    if isinstance(access, list):
        text = " ".join(str(item) for item in access).lower()
    elif access is None:
        return True, False, False
    else:
        text = str(access).lower()

    if text.isdigit():
        return AQARA_ACCESS_FLAGS.get(int(text), (False, False, False))

    tokens = {token for token in re.split(r"[^a-z0-9]+", text) if token}
    readable = bool(tokens & {"r", "read", "readable", "query", "queryable"}) or "read" in text
    writable = bool(tokens & {"w", "write", "writable", "set", "settable"}) or "write" in text
    reportable = bool(tokens & {"report", "reportable", "notify", "notifiable"}) or "report" in text
    if len(tokens) == 1:
        short_access = next(iter(tokens))
        if short_access in {"r", "rw", "wr"}:
            readable = True
        if short_access in {"w", "rw", "wr"}:
            writable = True

    return readable, writable, reportable


def _enum_value_map(enums: Any) -> dict[str, str]:
    if isinstance(enums, dict):
        return {str(key): str(value) for key, value in enums.items()}

    if isinstance(enums, str):
        values: dict[str, str] = {}
        for raw_item in enums.split(","):
            item = raw_item.strip()
            if not item:
                continue
            key, separator, label = item.partition(":")
            if not separator:
                key, separator, label = item.partition("=")
            key = key.strip()
            if key:
                values[key] = label.strip() if separator and label.strip() else key
        return values

    if not isinstance(enums, list):
        return {}

    values: dict[str, str] = {}
    for item in enums:
        if isinstance(item, dict):
            value = _first_value(item, ("value", "key", "code", "id", "enumValue"))
            label = _first_value(item, ("name", "label", "description", "desc", "text"))
            if value is not None:
                values[str(value)] = str(label if label is not None else value)
        elif item is not None:
            values[str(item)] = str(item)
    return values


def _resource_name(resource: dict[str, Any], resource_id: str) -> str:
    name = _first_value(resource, ("name", "resourceName", "displayName", "description", "desc"))
    if name is None:
        return f"Resource {resource_id}"
    return str(name).strip()


def _resource_translation_key(
    model: str,
    resource: dict[str, Any],
    resource_id: str,
) -> str | None:
    if model != SMOKE_SENSOR_MODEL:
        return None

    if translation_key := SMOKE_SENSOR_TRANSLATION_KEYS_BY_RESOURCE_ID.get(resource_id):
        return translation_key

    resource_name = _resource_name(resource, resource_id).casefold()
    return SMOKE_SENSOR_TRANSLATION_KEYS_BY_NAME.get(resource_name)


def _native_unit(resource: dict[str, Any]) -> str | None:
    unit = resource.get("unit")
    if not isinstance(unit, str):
        return None
    normalized = unit.strip()
    return normalized if normalized and not normalized.isdigit() else None


def _enabled_by_default(
    resource: dict[str, Any],
    resource_id: str,
    platform: str,
    *,
    writable: bool,
    reportable: bool,
) -> bool:
    if writable:
        return False

    if platform == CHILD_BINARY_SENSOR_PLATFORM and reportable:
        return True

    if _has_value(resource.get("unit")) and (reportable or platform == CHILD_SENSOR_PLATFORM):
        return True

    haystack = " ".join(
        str(value).lower()
        for value in (
            resource_id,
            resource.get("name"),
            resource.get("resourceName"),
            resource.get("displayName"),
            resource.get("description"),
            resource.get("desc"),
        )
        if _has_value(value)
    )
    return reportable and any(marker in haystack for marker in SAFE_DEFAULT_NAME_MARKERS)


def _resource_id(resource: dict[str, Any]) -> str:
    value = _first_value(resource, ("resourceId", "resourceID", "attr", "attribute", "id"))
    return "" if value is None else str(value).strip()


def _resource_to_spec(child: dict[str, Any], resource: dict[str, Any]) -> dict[str, Any] | None:
    resource_id = _resource_id(resource)
    if not resource_id:
        _LOGGER.debug("Ignoring Aqara child resource without resourceId: child=%s resource=%s", child.get("did"), resource)
        return None

    readable, writable, reportable = _access_flags(resource)
    if not readable:
        _LOGGER.debug(
            "Ignoring Aqara child resource because it is not readable: child=%s resource=%s access=%s",
            child.get("did"),
            resource_id,
            resource.get("access"),
        )
        return None

    enum_map = _enum_value_map(resource.get("enums") or resource.get("enum") or resource.get("values"))
    enum_values = set(enum_map)
    is_binary = enum_values == {"0", "1"}
    platform = CHILD_BINARY_SENSOR_PLATFORM if is_binary else CHILD_SENSOR_PLATFORM
    enabled_default = _enabled_by_default(
        resource,
        resource_id,
        platform,
        writable=writable,
        reportable=reportable,
    )

    model = str(child.get("model") or "")
    spec = {
        "api": resource_id,
        "key": resource_id,
        "inApp": resource_id,
        "unique_id": child_unique_id(str(child["did"]), resource_id),
        "resource_id": resource_id,
        "name": _resource_name(resource, resource_id),
        "description": resource.get("description") or resource.get("desc"),
        "unit": _native_unit(resource),
        "platform": platform,
        "did": str(child["did"]),
        "parent_did": str(child["parentDid"]),
        "model": model,
        "device_name": str(child.get("deviceName") or child.get("did") or ""),
        "firmware_version": child.get("firmwareVersion"),
        "readable": readable,
        "writable": writable,
        "reportable": reportable,
        "enabled_default": enabled_default,
        "value_type": "bool" if is_binary else "string",
        "value_map": {} if is_binary else enum_map,
        "raw_resource": resource,
    }
    translation_key = _resource_translation_key(model, resource, resource_id)
    if translation_key:
        spec["translation_key"] = translation_key
    _LOGGER.debug(
        "Mapped Aqara child resource: child=%s resource=%s platform=%s readable=%s writable=%s reportable=%s enabled_default=%s",
        child.get("did"),
        resource_id,
        platform,
        readable,
        writable,
        reportable,
        enabled_default,
    )
    return spec


def build_child_entity_specs(
    child_devices: list[dict[str, Any]],
    resource_info_by_model: dict[str, Any],
    skip_dids: set[str] | None = None,
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    skip_dids = skip_dids or set()

    for child in child_devices:
        did = str(child.get("did") or "").strip()
        if not did or did in skip_dids:
            continue
        model = str(child.get("model") or "").strip()
        resources = _flatten_resource_info(resource_info_by_model.get(model)) if model else []
        if not resources:
            _LOGGER.debug("No Aqara child resource info available for child=%s model=%s", did, model)
            continue
        for resource in resources:
            spec = _resource_to_spec(child, resource)
            if spec is not None:
                specs.append(spec)

    return specs


def child_specs_by_did(child_entity_specs: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for spec in child_entity_specs:
        grouped.setdefault(str(spec["did"]), []).append(spec)
    return grouped


def child_resource_spec_maps(child_entity_specs: Iterable[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    maps: dict[str, dict[str, dict[str, Any]]] = {}
    for spec in child_entity_specs:
        maps.setdefault(str(spec["did"]), {})[str(spec["resource_id"])] = spec
    return maps


def child_enabled_resource_ids(
    enabled_unique_ids: set[str],
    child_entity_specs: Iterable[dict[str, Any]],
    *,
    known_unique_ids: set[str] | None = None,
    reportable: bool | None = None,
) -> list[str]:
    resource_ids: dict[str, None] = {}
    for spec in child_entity_specs:
        if reportable is not None and bool(spec.get("reportable")) != reportable:
            continue
        unique_id = str(spec.get("unique_id") or "")
        if unique_id in enabled_unique_ids or (
            known_unique_ids is not None
            and spec.get("enabled_default", False)
            and unique_id not in known_unique_ids
        ):
            resource_ids[str(spec["resource_id"])] = None
    return list(resource_ids)


def build_child_active_subscriptions(
    enabled_unique_ids: set[str],
    child_entity_specs: Iterable[dict[str, Any]],
    *,
    known_unique_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    specs_by_did = child_specs_by_did(child_entity_specs)
    subscriptions: list[dict[str, Any]] = []
    for did, specs in specs_by_did.items():
        resource_ids = child_enabled_resource_ids(
            enabled_unique_ids,
            specs,
            known_unique_ids=known_unique_ids,
            reportable=True,
        )
        if resource_ids:
            subscriptions.append(
                {
                    "subjectId": did,
                    "resourceIds": resource_ids,
                    "attach": CHILD_SUBSCRIPTION_ATTACH,
                }
            )
    return subscriptions


def child_polling_required_dids(
    enabled_unique_ids: set[str],
    child_entity_specs: Iterable[dict[str, Any]],
    *,
    known_unique_ids: set[str] | None = None,
) -> set[str]:
    required: set[str] = set()
    for did, specs in child_specs_by_did(child_entity_specs).items():
        if child_enabled_resource_ids(
            enabled_unique_ids,
            specs,
            known_unique_ids=known_unique_ids,
            reportable=False,
        ):
            required.add(did)
    return required
