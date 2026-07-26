from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from .const import (
    CONF_HOMEKIT_ID,
    CONF_MANAGED_HOMEKIT,
    CONF_STREAM_NAME,
    G2H_PRO_DEVICE_LABEL,
    G3_DEVICE_LABEL,
    G410_DEVICE_LABEL,
    G4_DEVICE_LABEL,
)


def _string_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def build_camera_candidate(device: Mapping[str, Any], label: str) -> dict[str, str]:
    did = _string_value(device.get("did"))
    return {
        "did": did,
        "deviceName": _string_value(device.get("deviceName"), did),
        "model": _string_value(device.get("model")),
        "label": label,
    }


def build_camera_candidates(
    cameras: list[dict[str, Any]],
    g2h_pro_cameras: list[dict[str, Any]],
    g410_doorbells: list[dict[str, Any]],
    g4_doorbells: list[dict[str, Any]],
) -> list[dict[str, str]]:
    candidates = [
        *(build_camera_candidate(camera, G3_DEVICE_LABEL) for camera in cameras),
        *(build_camera_candidate(camera, G2H_PRO_DEVICE_LABEL) for camera in g2h_pro_cameras),
        *(build_camera_candidate(doorbell, G410_DEVICE_LABEL) for doorbell in g410_doorbells),
        *(build_camera_candidate(doorbell, G4_DEVICE_LABEL) for doorbell in g4_doorbells),
    ]
    return [candidate for candidate in candidates if candidate["did"]]


def stream_name_for_did(did: str) -> str:
    safe_did = re.sub(r"[^A-Za-z0-9_-]+", "_", did).strip("_").lower()
    return f"ha_aqara_{safe_did}"


def normalize_stream_config(config: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(config, Mapping):
        return None
    stream_name = _string_value(config.get(CONF_STREAM_NAME))
    if not stream_name:
        return None
    return {
        CONF_STREAM_NAME: stream_name,
        CONF_MANAGED_HOMEKIT: bool(config.get(CONF_MANAGED_HOMEKIT, False)),
        CONF_HOMEKIT_ID: _string_value(config.get(CONF_HOMEKIT_ID)),
    }


def stream_config_for_did(options: Mapping[str, Any] | None, did: str) -> dict[str, Any] | None:
    if not isinstance(options, Mapping):
        return None
    return normalize_stream_config(options.get(did))


def has_managed_camera_streams(options: Mapping[str, Any] | None) -> bool:
    if not isinstance(options, Mapping):
        return False
    return any(
        config is not None and config[CONF_MANAGED_HOMEKIT]
        for value in options.values()
        if (config := normalize_stream_config(value)) is not None
    )


def build_rtsp_stream_url(base_url: str, stream_name: str) -> str | None:
    value = _string_value(base_url).rstrip("/")
    if not value or not stream_name:
        return None
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "rtsp" or not parsed.netloc:
        return None
    try:
        if not parsed.hostname:
            return None
        parsed.port
    except ValueError:
        return None
    path = f"{parsed.path.rstrip('/')}/{quote(stream_name, safe='._-')}"
    # HomeKit uses AAC-ELD audio, which needs a separate go2rtc/FFmpeg
    # transcoding source before it can be exposed reliably to Home Assistant.
    return urlunsplit((parsed.scheme, parsed.netloc, path, "video", ""))
