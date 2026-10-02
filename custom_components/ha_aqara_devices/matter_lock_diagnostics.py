"""Collect capability metadata only; never retain device values or credentials."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from .const import EXPERIMENTAL_MATTER_LOCK_MODELS

CAPABILITY_TIMEOUT_SECONDS = 20
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,79}\Z")
_TYPES = {"Bool", "Integer", "Float", "String", "Struct", "Enum", "Data"}


def _code(value: Any) -> str | None:
    return value if isinstance(value, str) and _CODE.fullmatch(value) else None


def _items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def sanitize_capabilities(response: Any, model: str) -> dict[str, Any]:
    """Allowlist schema metadata, excluding values, defaults, enums and errors."""
    if not isinstance(response, dict):
        return {"status": "invalid_response"}
    if str(response.get("code")) != "0":
        return {"status": "api_error"}
    result = response.get("result")
    devices = _items(result.get("data") if isinstance(result, dict) else result)
    endpoints = []
    for device in devices:
        if device.get("model") != model:
            continue
        for endpoint in _items(device.get("endpoints")):
            endpoint_id = endpoint.get("endpointId")
            if type(endpoint_id) is not int or endpoint_id < 0:
                continue
            functions = []
            for function in _items(endpoint.get("functions")):
                function_code = _code(function.get("functionCode"))
                if function_code is None:
                    continue
                traits = []
                for trait in _items(function.get("traits")):
                    trait_code = _code(trait.get("traitCode"))
                    if trait_code is None:
                        continue
                    metadata: dict[str, Any] = {"traitCode": trait_code}
                    trait_id = trait.get("traitId")
                    if type(trait_id) is int and trait_id >= 0:
                        metadata["traitId"] = trait_id
                    parameter = trait.get("parameter", trait.get("attribute"))
                    if isinstance(parameter, dict):
                        for flag in ("readable", "writable", "subscribable"):
                            if type(parameter.get(flag)) is bool:
                                metadata[flag] = parameter[flag]
                        data_type = parameter.get("type")
                        if isinstance(data_type, str) and (
                            data_type in _TYPES
                            or data_type in {f"List[{item}]" for item in _TYPES}
                        ):
                            metadata["type"] = data_type
                    traits.append(metadata)
                functions.append({"functionCode": function_code, "traits": traits})
            endpoints.append({"endpointId": endpoint_id, "functions": functions})
    return {"status": "success" if endpoints else "no_capabilities", "endpoints": endpoints}


async def collect_lock_capabilities(api: Any, locks: list[dict[str, Any]], cache: list[dict[str, Any]]) -> None:
    """Best-effort collection, bounded per lock and cancellable on unload."""
    for lock in locks:
        model = lock.get("model")
        if model not in EXPERIMENTAL_MATTER_LOCK_MODELS:
            continue
        record: dict[str, Any] = {"model": model, "status": "pending"}
        cache.append(record)
        try:
            async with asyncio.timeout(CAPABILITY_TIMEOUT_SECONDS):
                response = await api.query_matter_device_config([lock["did"]])
                metadata = sanitize_capabilities(response, model)
        except TimeoutError:
            metadata = {"status": "timeout"}
        except Exception:
            # Exception text and API messages can include tokens and raw values.
            metadata = {"status": "request_failed"}
        record.update(metadata)
