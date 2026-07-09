from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, unquote, urlparse

from .const import (
    CONF_RTSP_ENABLED,
    CONF_RTSP_HOST,
    CONF_RTSP_PASSWORD,
    CONF_RTSP_PATH,
    CONF_RTSP_PORT,
    CONF_RTSP_USERNAME,
    DEFAULT_RTSP_PATH,
    DEFAULT_RTSP_PORT,
    G2H_PRO_DEVICE_LABEL,
    G3_DEVICE_LABEL,
    G410_DEVICE_LABEL,
    G4_DEVICE_LABEL,
)


def _string_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _port_value(value: Any, default: int = DEFAULT_RTSP_PORT) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    if port < 1 or port > 65535:
        return default
    return port


def _valid_port_value(value: Any) -> bool:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= port <= 65535


def _bool_value(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", "disabled"}
    return bool(value)


def _rtsp_url_parts(value: str) -> dict[str, Any]:
    if not value:
        return {}

    parsed = urlparse(value if "://" in value else f"//{value}", allow_fragments=False)
    if parsed.scheme and parsed.scheme.lower() != "rtsp":
        return {}

    try:
        port = parsed.port
    except ValueError:
        port = None

    return {
        "host": parsed.hostname or value,
        "port": port,
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "path": parsed.path.lstrip("/"),
    }


def normalize_rtsp_path(path: Any) -> str:
    normalized = _string_value(path, DEFAULT_RTSP_PATH).lstrip("/")
    return normalized or DEFAULT_RTSP_PATH


def normalize_rtsp_camera_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    config = config or {}
    host_input = _string_value(config.get(CONF_RTSP_HOST))
    url_parts = _rtsp_url_parts(host_input)
    host = ""
    if "://" not in host_input or url_parts:
        host = _string_value(url_parts.get("host") or host_input)

    path_input = normalize_rtsp_path(config.get(CONF_RTSP_PATH, DEFAULT_RTSP_PATH))
    parsed_path = normalize_rtsp_path(url_parts.get("path") or DEFAULT_RTSP_PATH)
    if url_parts.get("path") and path_input == DEFAULT_RTSP_PATH:
        path = parsed_path
    else:
        path = path_input

    username = _string_value(config.get(CONF_RTSP_USERNAME))
    if not username:
        username = _string_value(url_parts.get("username"))

    password = _string_value(config.get(CONF_RTSP_PASSWORD))
    if not password:
        password = _string_value(url_parts.get("password"))

    port = _port_value(config.get(CONF_RTSP_PORT, url_parts.get("port") or DEFAULT_RTSP_PORT))
    if url_parts.get("port") and config.get(CONF_RTSP_PORT) in (None, "", DEFAULT_RTSP_PORT):
        port = _port_value(url_parts["port"])

    return {
        CONF_RTSP_ENABLED: _bool_value(config.get(CONF_RTSP_ENABLED), True),
        CONF_RTSP_HOST: host,
        CONF_RTSP_PORT: port,
        CONF_RTSP_USERNAME: username,
        CONF_RTSP_PASSWORD: password,
        CONF_RTSP_PATH: path,
    }


def has_rtsp_stream_config(config: Mapping[str, Any] | None) -> bool:
    normalized = normalize_rtsp_camera_config(config)
    return bool(
        normalized[CONF_RTSP_ENABLED]
        and normalized[CONF_RTSP_HOST]
        and normalized[CONF_RTSP_PATH]
        and 1 <= normalized[CONF_RTSP_PORT] <= 65535
    )


def can_save_rtsp_camera_config(config: Mapping[str, Any] | None) -> bool:
    if not isinstance(config, Mapping):
        return False

    normalized = normalize_rtsp_camera_config(config)
    if not normalized[CONF_RTSP_ENABLED]:
        return True

    if config.get(CONF_RTSP_PORT) not in (None, "") and not _valid_port_value(config[CONF_RTSP_PORT]):
        return False

    if config.get(CONF_RTSP_PATH) is not None and not _string_value(config[CONF_RTSP_PATH]):
        return False

    return bool(
        normalized[CONF_RTSP_HOST]
        and normalized[CONF_RTSP_PATH]
        and 1 <= normalized[CONF_RTSP_PORT] <= 65535
    )


def rtsp_config_for_did(options: Mapping[str, Any] | None, did: str) -> dict[str, Any] | None:
    if not isinstance(options, Mapping):
        return None
    config = options.get(did)
    if not isinstance(config, Mapping):
        return None
    normalized = normalize_rtsp_camera_config(config)
    if not has_rtsp_stream_config(normalized):
        return None
    return normalized


def build_rtsp_url(config: Mapping[str, Any] | None) -> str | None:
    if not has_rtsp_stream_config(config):
        return None

    normalized = normalize_rtsp_camera_config(config)
    host = normalized[CONF_RTSP_HOST]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    credentials = ""
    username = normalized[CONF_RTSP_USERNAME]
    password = normalized[CONF_RTSP_PASSWORD]
    if username:
        credentials = quote(username, safe="")
        if password:
            credentials = f"{credentials}:{quote(password, safe='')}"
        credentials = f"{credentials}@"

    path = quote(normalized[CONF_RTSP_PATH].lstrip("/"), safe="/")
    return f"rtsp://{credentials}{host}:{normalized[CONF_RTSP_PORT]}/{path}"


def mask_rtsp_url(config: Mapping[str, Any] | None) -> str | None:
    if not has_rtsp_stream_config(config):
        return None

    normalized = normalize_rtsp_camera_config(config)
    host = normalized[CONF_RTSP_HOST]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    credentials = "***:***@" if normalized[CONF_RTSP_USERNAME] else ""
    path = quote(normalized[CONF_RTSP_PATH].lstrip("/"), safe="/")
    return f"rtsp://{credentials}{host}:{normalized[CONF_RTSP_PORT]}/{path}"


def build_rtsp_candidate(
    device: Mapping[str, Any],
    label: str,
) -> dict[str, str]:
    return {
        "did": _string_value(device.get("did")),
        "deviceName": _string_value(device.get("deviceName"), _string_value(device.get("did"))),
        "model": _string_value(device.get("model")),
        "label": label,
    }


def build_rtsp_candidate_cameras(
    cameras: list[dict[str, Any]],
    g2h_pro_cameras: list[dict[str, Any]],
    g410_doorbells: list[dict[str, Any]],
    g4_doorbells: list[dict[str, Any]],
) -> list[dict[str, str]]:
    candidates = [
        *(build_rtsp_candidate(camera, G3_DEVICE_LABEL) for camera in cameras),
        *(build_rtsp_candidate(camera, G2H_PRO_DEVICE_LABEL) for camera in g2h_pro_cameras),
        *(build_rtsp_candidate(doorbell, G410_DEVICE_LABEL) for doorbell in g410_doorbells),
        *(build_rtsp_candidate(doorbell, G4_DEVICE_LABEL) for doorbell in g4_doorbells),
    ]
    return [candidate for candidate in candidates if candidate["did"]]
