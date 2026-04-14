from __future__ import annotations

from typing import Any, Iterable

from .binary_sensors import ALL_BINARY_SENSORS_DEF, GESTURE_RESOURCE_ID, GESTURE_SENSORS, M3_BINARY_SENSORS_DEF
from .const import FP2_MODEL, FP300_MODEL
from .fp2 import FP2_BINARY_SENSORS_DEF, FP2_SENSOR_SPECS
from .fp300 import FP300_BINARY_SENSORS_DEF, FP300_SENSOR_SPECS
from .numbers import ALL_NUMBERS_DEF, M3_NUMBERS_DEF
from .selects import M3_SELECTS_DEF
from .sensors import M3_SENSORS_DEF
from .switches import ALL_SWITCHES_DEF


def spec_state_key(spec: dict[str, Any]) -> str:
    return str(spec.get("key") or spec.get("inApp") or "")


def build_api_spec_map(specs: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(spec["api"]): spec
        for spec in specs
        if spec.get("api") and spec_state_key(spec)
    }


def unique_api_resource_ids(specs: Iterable[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for spec in specs:
        api = spec.get("api")
        if api:
            seen[str(api)] = None
    return list(seen)


def _to01(value: Any) -> int:
    try:
        return 1 if int(value) == 1 else 0
    except Exception:
        return 1 if str(value).strip().lower() in ("1", "on", "true", "yes") else 0


def coerce_spec_value(spec: dict[str, Any], value: Any, *, apply_scale: bool) -> Any:
    if value is None:
        return spec.get("default", 0)

    value_type = spec.get("value_type") or spec.get("type")
    if value_type in ("int", "integer", "uint8_t", "uint16_t", "uint32_t"):
        try:
            parsed: Any = int(float(value))
        except Exception:
            parsed = 0
    elif value_type == "float":
        try:
            parsed = float(value)
        except Exception:
            parsed = 0.0
    elif value_type in ("string", "str"):
        parsed = "" if value is None else str(value)
    elif value_type == "bool":
        parsed = _to01(value)
    else:
        parsed = _to01(value)

    scale = spec.get("scale")
    if apply_scale and scale is not None:
        try:
            parsed = float(parsed) * float(scale)
        except Exception:
            pass
    return parsed


G3_STATE_SPECS = [
    *ALL_BINARY_SENSORS_DEF,
    *ALL_NUMBERS_DEF,
    *ALL_SWITCHES_DEF,
]
G3_RESOURCE_SPEC_MAP = build_api_spec_map(G3_STATE_SPECS)
G3_SUBSCRIPTION_RESOURCE_IDS = [*unique_api_resource_ids(G3_STATE_SPECS), GESTURE_RESOURCE_ID]
G3_GESTURE_VALUE_MAP = {
    str(spec["history_value"]): spec["inApp"]
    for spec in GESTURE_SENSORS
}


M3_STATE_SPECS = [
    *M3_BINARY_SENSORS_DEF,
    *M3_SENSORS_DEF,
    *M3_NUMBERS_DEF,
    *M3_SELECTS_DEF,
]
M3_RESOURCE_SPEC_MAP = build_api_spec_map(M3_STATE_SPECS)
M3_SUBSCRIPTION_RESOURCE_IDS = unique_api_resource_ids(M3_STATE_SPECS)


FP2_STATE_SPECS = [
    *FP2_BINARY_SENSORS_DEF,
    *FP2_SENSOR_SPECS,
]
FP2_ON_BED_SPEC = {
    "name": "On Bed",
    "key": "on_bed_status",
    "api": "3.52.85",
    "poll_group": "presence",
    "value_type": "int",
    "enabled_default": False,
}
FP2_GROUP_SPECS = {
    group: [spec for spec in FP2_STATE_SPECS if spec.get("poll_group") == group and spec.get("api")]
    for group in ("fast", "presence", "medium", "slow")
}
FP2_GROUP_SPECS["presence"] = [*FP2_GROUP_SPECS["presence"], FP2_ON_BED_SPEC]
FP2_GROUP_SPEC_MAPS = {
    group: build_api_spec_map(specs)
    for group, specs in FP2_GROUP_SPECS.items()
}
FP2_SUBSCRIPTION_RESOURCE_IDS = unique_api_resource_ids(
    [spec for specs in FP2_GROUP_SPECS.values() for spec in specs]
)


FP300_STATE_SPECS = [
    *FP300_BINARY_SENSORS_DEF,
    *FP300_SENSOR_SPECS,
]
FP300_GROUP_SPECS = {
    group: [spec for spec in FP300_STATE_SPECS if spec.get("poll_group") == group and spec.get("api")]
    for group in ("fast", "medium", "slow")
}
FP300_GROUP_SPEC_MAPS = {
    group: build_api_spec_map(specs)
    for group, specs in FP300_GROUP_SPECS.items()
}
FP300_SUBSCRIPTION_RESOURCE_IDS = unique_api_resource_ids(FP300_STATE_SPECS)


def _spec_resource_id(spec: dict[str, Any]) -> str | None:
    resource_id = spec.get("api") or spec.get("history_resource")
    if not resource_id:
        return None
    return str(resource_id)


def _append_resource_if_enabled(
    resource_ids: dict[str, None],
    enabled_unique_ids: set[str],
    unique_id: str,
    spec: dict[str, Any],
) -> None:
    if unique_id not in enabled_unique_ids:
        return
    resource_id = _spec_resource_id(spec)
    if resource_id:
        resource_ids[resource_id] = None


def _collect_g3_resources(enabled_unique_ids: set[str], did: str) -> list[str]:
    resource_ids: dict[str, None] = {}
    for spec in G3_STATE_SPECS:
        _append_resource_if_enabled(resource_ids, enabled_unique_ids, f"{did}_{spec['inApp']}", spec)
    return list(resource_ids)


def _collect_m3_resources(enabled_unique_ids: set[str], did: str) -> list[str]:
    resource_ids: dict[str, None] = {}
    for spec in M3_STATE_SPECS:
        _append_resource_if_enabled(resource_ids, enabled_unique_ids, f"{did}_{spec['inApp']}", spec)
    return list(resource_ids)


def _collect_presence_resources(
    enabled_unique_ids: set[str],
    did: str,
    binary_specs: Iterable[dict[str, Any]],
    sensor_specs: Iterable[dict[str, Any]],
) -> list[str]:
    resource_ids: dict[str, None] = {}
    for spec in binary_specs:
        _append_resource_if_enabled(resource_ids, enabled_unique_ids, f"{did}_fp2_{spec['key']}", spec)
    for spec in sensor_specs:
        _append_resource_if_enabled(resource_ids, enabled_unique_ids, f"{did}_fp2_sensor_{spec['key']}", spec)
    return list(resource_ids)


def build_active_subscriptions(
    enabled_unique_ids: set[str],
    cameras: list[dict[str, Any]],
    hubs_m3: list[dict[str, Any]],
    presence_devices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    subscriptions: list[dict[str, Any]] = []

    for camera in cameras:
        did = str(camera["did"])
        resource_ids = _collect_g3_resources(enabled_unique_ids, did)
        if resource_ids:
            subscriptions.append({"subjectId": did, "resourceIds": resource_ids})

    for hub in hubs_m3:
        did = str(hub["did"])
        resource_ids = _collect_m3_resources(enabled_unique_ids, did)
        if resource_ids:
            subscriptions.append({"subjectId": did, "resourceIds": resource_ids})

    for presence in presence_devices:
        did = str(presence["did"])
        model = str(presence.get("model") or "")
        if model == FP2_MODEL:
            resource_ids = _collect_presence_resources(
                enabled_unique_ids,
                did,
                FP2_BINARY_SENSORS_DEF,
                FP2_SENSOR_SPECS,
            )
        elif model == FP300_MODEL:
            resource_ids = _collect_presence_resources(
                enabled_unique_ids,
                did,
                FP300_BINARY_SENSORS_DEF,
                FP300_SENSOR_SPECS,
            )
        else:
            continue

        if resource_ids:
            subscriptions.append({"subjectId": did, "resourceIds": resource_ids})

    return subscriptions
