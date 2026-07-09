from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.ha_aqara_devices"
PACKAGE_PATH = ROOT / "custom_components" / "ha_aqara_devices"


def _load_module(name: str):
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    sys.modules["custom_components"].__path__ = [str(ROOT / "custom_components")]

    package = sys.modules.setdefault(PACKAGE, types.ModuleType(PACKAGE))
    package.__path__ = [str(PACKAGE_PATH)]

    module_name = f"{PACKAGE}.{name}"
    spec = importlib.util.spec_from_file_location(module_name, PACKAGE_PATH / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


const = _load_module("const")
camera_config = _load_module("camera_config")


def test_build_rtsp_url_without_credentials():
    url = camera_config.build_rtsp_url(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "camera.local",
            const.CONF_RTSP_PORT: 8554,
            const.CONF_RTSP_PATH: "/ch1",
        }
    )

    assert url == "rtsp://camera.local:8554/ch1"


def test_build_rtsp_url_escapes_credentials():
    url = camera_config.build_rtsp_url(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "192.0.2.10",
            const.CONF_RTSP_PORT: 8554,
            const.CONF_RTSP_USERNAME: "user@example.com",
            const.CONF_RTSP_PASSWORD: "p:a@s# word",
            const.CONF_RTSP_PATH: "720p",
        }
    )

    assert url == "rtsp://user%40example.com:p%3Aa%40s%23%20word@192.0.2.10:8554/720p"


def test_normalize_rtsp_config_from_full_url():
    normalized = camera_config.normalize_rtsp_camera_config(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "rtsp://rtsp-user:pa%23ss@192.0.2.10:8555/1080p",
            const.CONF_RTSP_PORT: const.DEFAULT_RTSP_PORT,
            const.CONF_RTSP_PATH: const.DEFAULT_RTSP_PATH,
        }
    )

    assert normalized == {
        const.CONF_RTSP_ENABLED: True,
        const.CONF_RTSP_HOST: "192.0.2.10",
        const.CONF_RTSP_PORT: 8555,
        const.CONF_RTSP_USERNAME: "rtsp-user",
        const.CONF_RTSP_PASSWORD: "pa#ss",
        const.CONF_RTSP_PATH: "1080p",
    }


def test_invalid_and_disabled_configs_are_not_streamable():
    assert not camera_config.has_rtsp_stream_config(
        {
            const.CONF_RTSP_ENABLED: "false",
            const.CONF_RTSP_HOST: "camera.local",
            const.CONF_RTSP_PATH: "ch1",
        }
    )
    assert not camera_config.has_rtsp_stream_config(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "",
            const.CONF_RTSP_PATH: "ch1",
        }
    )
    assert not camera_config.has_rtsp_stream_config(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "https://camera.local/stream",
            const.CONF_RTSP_PATH: "ch1",
        }
    )
    assert not camera_config.can_save_rtsp_camera_config(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "camera.local",
            const.CONF_RTSP_PORT: 70000,
            const.CONF_RTSP_PATH: "ch1",
        }
    )


def test_mask_rtsp_url_hides_credentials():
    masked = camera_config.mask_rtsp_url(
        {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "camera.local",
            const.CONF_RTSP_PORT: 8554,
            const.CONF_RTSP_USERNAME: "admin",
            const.CONF_RTSP_PASSWORD: "secret",
            const.CONF_RTSP_PATH: "ch1",
        }
    )

    assert masked == "rtsp://***:***@camera.local:8554/ch1"
    assert "admin" not in masked
    assert "secret" not in masked


def test_rtsp_config_lookup_handles_multiple_cameras():
    options = {
        "did-1": {
            const.CONF_RTSP_ENABLED: True,
            const.CONF_RTSP_HOST: "camera-a.local",
            const.CONF_RTSP_PATH: "ch1",
        },
        "did-2": {
            const.CONF_RTSP_ENABLED: False,
            const.CONF_RTSP_HOST: "camera-b.local",
            const.CONF_RTSP_PATH: "ch1",
        },
    }

    assert camera_config.rtsp_config_for_did(options, "did-1")[const.CONF_RTSP_HOST] == "camera-a.local"
    assert camera_config.rtsp_config_for_did(options, "did-2") is None
    assert camera_config.rtsp_config_for_did(options, "missing") is None


def test_disabled_rtsp_config_can_be_saved_but_is_not_streamable():
    saved_config = camera_config.normalize_rtsp_camera_config(
        {
            const.CONF_RTSP_ENABLED: False,
            const.CONF_RTSP_HOST: "camera.local",
            const.CONF_RTSP_PORT: 8554,
            const.CONF_RTSP_USERNAME: "admin",
            const.CONF_RTSP_PASSWORD: "secret",
            const.CONF_RTSP_PATH: "ch1",
        }
    )
    stored_options = {"did-1": saved_config}

    assert camera_config.can_save_rtsp_camera_config(saved_config)
    assert stored_options["did-1"] == saved_config
    assert camera_config.rtsp_config_for_did(stored_options, "did-1") is None
    assert camera_config.build_rtsp_url(saved_config) is None


def test_build_rtsp_candidate_cameras_preserves_labels_and_filters_missing_did():
    candidates = camera_config.build_rtsp_candidate_cameras(
        [{"did": "g3", "deviceName": "Office", "model": "lumi.camera.gwpgl1"}],
        [{"did": "g2h", "deviceName": "Hall", "model": "lumi.camera.agl001"}],
        [{"deviceName": "No DID", "model": "lumi.camera.acn017"}],
        [{"did": "g4", "deviceName": "Door", "model": "lumi.camera.agl002"}],
    )

    assert candidates == [
        {
            "did": "g3",
            "deviceName": "Office",
            "model": "lumi.camera.gwpgl1",
            "label": const.G3_DEVICE_LABEL,
        },
        {
            "did": "g2h",
            "deviceName": "Hall",
            "model": "lumi.camera.agl001",
            "label": const.G2H_PRO_DEVICE_LABEL,
        },
        {
            "did": "g4",
            "deviceName": "Door",
            "model": "lumi.camera.agl002",
            "label": const.G4_DEVICE_LABEL,
        },
    ]
