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
