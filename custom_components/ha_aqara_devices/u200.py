from __future__ import annotations

from typing import Any

from homeassistant.const import PERCENTAGE, UnitOfElectricPotential

U200_BASIC_ENDPOINT_ID = 0
U200_POWER_ENDPOINT_ID = 1
U200_LOCK_ENDPOINT_ID = 2
U200_LOCK_FUNCTION = "DoorLock"

U200_LOCK_STATE_LOCKED = "1"
U200_LOCK_STATE_UNLOCKED = {"0", "2", "3"}
U200_LOCK_STATE_LABELS = {
    "0": "not_fully_locked",
    "1": "locked",
    "2": "unlocked",
    "3": "unlatched",
}

U200_DOOR_STATE_LABELS = {
    "0": "open",
    "1": "closed",
    "2": "jammed",
    "3": "forced_open",
    "4": "unspecified_error",
    "5": "ajar",
}

U200_REACHABLE = {
    "name": "Reachable",
    "translation_key": "reachable",
    "icon": "mdi:lan-connect",
    "inApp": "reachable",
    "device_class": "connectivity",
    "value_type": "bool",
}

U200_BATTERY_REPLACEMENT_NEEDED = {
    "name": "Battery Replacement Needed",
    "translation_key": "battery_replacement_needed",
    "icon": "mdi:battery-alert",
    "inApp": "battery_replacement_needed",
    "device_class": "problem",
    "value_type": "bool",
}

U200_BINARY_SENSORS_DEF = [
    U200_REACHABLE,
    U200_BATTERY_REPLACEMENT_NEEDED,
]

U200_BATTERY_PERCENTAGE = {
    "name": "Battery",
    "translation_key": "battery",
    "icon": "mdi:battery",
    "inApp": "battery_percentage",
    "device_class": "battery",
    "state_class": "measurement",
    "unit": PERCENTAGE,
    "default": None,
}

U200_CURRENT_VOLTAGE = {
    "name": "Battery Voltage",
    "translation_key": "battery_voltage",
    "icon": "mdi:sine-wave",
    "inApp": "current_voltage",
    "device_class": "voltage",
    "state_class": "measurement",
    "unit": UnitOfElectricPotential.VOLT,
    "default": None,
}

U200_SENSORS_DEF = [
    U200_BATTERY_PERCENTAGE,
    U200_CURRENT_VOLTAGE,
]

U200_STATE_TRAITS = [
    {
        "key": "reachable",
        "endpoint_id": U200_BASIC_ENDPOINT_ID,
        "function_code": "BasicInformation",
        "trait_code": "Reachable",
        "value_type": "bool",
        "default": None,
    },
    {
        "key": "battery_replacement_needed",
        "endpoint_id": U200_POWER_ENDPOINT_ID,
        "function_code": "PowerSource",
        "trait_code": "BatReplacementNeeded",
        "value_type": "bool",
        "default": None,
    },
    {
        "key": "rechargeable",
        "endpoint_id": U200_POWER_ENDPOINT_ID,
        "function_code": "PowerSource",
        "trait_code": "Rechargeable",
        "value_type": "bool",
        "default": None,
    },
    {
        "key": "current_voltage",
        "endpoint_id": U200_POWER_ENDPOINT_ID,
        "function_code": "PowerSource",
        "trait_code": "CurrentVoltage",
        "value_type": "float",
        "default": None,
    },
    {
        "key": "battery_percentage",
        "endpoint_id": U200_POWER_ENDPOINT_ID,
        "function_code": "PowerSource",
        "trait_code": "BatPercentRemaining",
        "value_type": "float",
        "default": None,
    },
    {
        "key": "lock_state",
        "endpoint_id": U200_LOCK_ENDPOINT_ID,
        "function_code": U200_LOCK_FUNCTION,
        "trait_code": "LockState",
        "value_type": "string",
        "default": None,
    },
    {
        "key": "door_state",
        "endpoint_id": U200_LOCK_ENDPOINT_ID,
        "function_code": U200_LOCK_FUNCTION,
        "trait_code": "DoorState",
        "value_type": "string",
        "default": None,
    },
]

U200_TRAIT_SPEC_MAP = {
    (spec["endpoint_id"], spec["function_code"], spec["trait_code"]): spec
    for spec in U200_STATE_TRAITS
}


def u200_trait_code_path(spec: dict[str, Any]) -> str:
    return f"{spec['endpoint_id']}.{spec['function_code']}.{spec['trait_code']}"


U200_TRAIT_CODE_PATH_MAP = {
    u200_trait_code_path(spec): spec for spec in U200_STATE_TRAITS
}


def build_u200_trait_subscriptions(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    code_paths = [u200_trait_code_path(spec) for spec in U200_STATE_TRAITS]
    return [
        {
            "deviceId": str(device["did"]),
            "codePaths": code_paths,
            "attach": "ha_aqara_devices",
        }
        for device in devices
    ]


def coerce_u200_trait_value(spec: dict[str, Any], value: Any) -> Any:
    if value is None:
        return spec.get("default")

    value_type = spec.get("value_type")
    if value_type == "bool":
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
        return bool(value)
    if value_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return spec.get("default")
    if value_type == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return spec.get("default")
    return str(value)


def u200_trait_request(device_id: str, spec: dict[str, Any], value: Any | None = None) -> dict[str, Any]:
    request = {
        "deviceId": device_id,
        "endpointId": spec["endpoint_id"],
        "functionCode": spec["function_code"],
        "traitCode": spec["trait_code"],
    }
    if value is not None:
        request["value"] = value
    return request
