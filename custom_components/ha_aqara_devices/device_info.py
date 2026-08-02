from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def build_device_info(did: str, device_name: str, model: str, label: str) -> DeviceInfo:
    return {
        "identifiers": {(DOMAIN, did)},
        "manufacturer": "Aqara",
        "model": model,
        "name": f"{label} ({device_name})",
        "model_id": did,
    }


def build_child_device_info(
    did: str,
    parent_did: str,
    device_name: str,
    model: str,
    firmware_version: str | None = None,
) -> DeviceInfo:
    info: DeviceInfo = {
        "identifiers": {(DOMAIN, did)},
        "manufacturer": "Aqara",
        "model": model or "Aqara child device",
        "name": device_name or model or did,
        "model_id": model or did,
        "via_device": (DOMAIN, parent_did),
    }
    if firmware_version:
        info["sw_version"] = firmware_version
    return info
