from __future__ import annotations

import asyncio
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

aiohttp = types.ModuleType("aiohttp")
aiohttp.BasicAuth = lambda username, password: (username, password)


class _ClientResponseError(Exception):
    status = 500


aiohttp.ClientResponseError = _ClientResponseError
aiohttp.ClientSession = object
sys.modules.setdefault("aiohttp", aiohttp)
go2rtc_client = _load_module("go2rtc_client")


def test_stream_name_for_did_is_stable_and_safe():
    assert camera_config.stream_name_for_did("lumi.1234/AB:CD") == "ha_aqara_lumi_1234_ab_cd"


def test_build_rtsp_stream_url_preserves_credentials_and_encodes_name():
    url = camera_config.build_rtsp_stream_url(
        "rtsp://user:p%40ss@camera.local:8554/base/",
        "Aqara Office",
    )

    assert url == "rtsp://user:p%40ss@camera.local:8554/base/Aqara%20Office?video"


def test_build_rtsp_stream_url_rejects_invalid_base_url():
    assert camera_config.build_rtsp_stream_url("https://camera.local", "camera") is None
    assert camera_config.build_rtsp_stream_url("rtsp://camera.local:not-a-port", "camera") is None
    assert camera_config.build_rtsp_stream_url("rtsp://camera.local:70000", "camera") is None
    assert camera_config.build_rtsp_stream_url("rtsp://camera.local", "") is None


def test_stream_config_lookup_handles_managed_and_external_streams():
    options = {
        "did-1": {
            const.CONF_STREAM_NAME: "managed",
            const.CONF_MANAGED_HOMEKIT: True,
            const.CONF_HOMEKIT_ID: "managed",
        },
        "did-2": {const.CONF_STREAM_NAME: "external"},
    }

    assert camera_config.stream_config_for_did(options, "did-1") == {
        const.CONF_STREAM_NAME: "managed",
        const.CONF_MANAGED_HOMEKIT: True,
        const.CONF_HOMEKIT_ID: "managed",
    }
    assert camera_config.stream_config_for_did(options, "did-2") == {
        const.CONF_STREAM_NAME: "external",
        const.CONF_MANAGED_HOMEKIT: False,
        const.CONF_HOMEKIT_ID: "",
    }
    assert camera_config.stream_config_for_did(options, "missing") is None
    assert camera_config.has_managed_camera_streams(options)
    assert not camera_config.has_managed_camera_streams({"did-2": options["did-2"]})
    assert not camera_config.has_managed_camera_streams(None)


def test_build_camera_candidates_preserves_labels_and_filters_missing_did():
    candidates = camera_config.build_camera_candidates(
        [{"did": "g3", "deviceName": "Office", "model": "lumi.camera.gwpgl1"}],
        [{"did": "g2h", "deviceName": "Hall", "model": "lumi.camera.agl001"}],
        [{"deviceName": "No DID", "model": "lumi.camera.acn017"}],
        [{"did": "g4", "deviceName": "Door", "model": "lumi.camera.agl002"}],
    )

    assert [candidate["did"] for candidate in candidates] == ["g3", "g2h", "g4"]
    assert candidates[0]["label"] == const.G3_DEVICE_LABEL
    assert candidates[1]["label"] == const.G2H_PRO_DEVICE_LABEL
    assert candidates[2]["label"] == const.G4_DEVICE_LABEL


class _FakeResponse:
    def __init__(self, payload=None, body: bytes = b"") -> None:
        self.payload = payload
        self.body = body
        self.status = 200

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def raise_for_status(self) -> None:
        return None

    async def json(self, content_type=None):
        return self.payload

    async def read(self) -> bytes:
        return self.body


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, object, object]] = []

    def request(self, method, url, *, params=None, data=None, auth=None, timeout=None):
        self.calls.append((method, url, params, data))
        return self.responses.pop(0)


def test_go2rtc_discovery_and_pairing_api():
    session = _FakeSession(
        [
            _FakeResponse(
                {
                    "sources": [
                        {"name": "Camera-Hub-G3-AB12", "url": "homekit://192.0.2.10:12345"},
                        {
                            "name": "Already paired",
                            "url": "homekit://192.0.2.11:12345",
                            "location": "existing_stream",
                        },
                        {"name": "Invalid"},
                    ]
                }
            ),
            _FakeResponse(),
        ]
    )
    client = go2rtc_client.Go2RtcClient(session, "http://go2rtc:1984")

    cameras = asyncio.run(client.discover_homekit())
    asyncio.run(client.pair_homekit("ha_aqara_g3", cameras[0].url, "123-45-678"))

    assert cameras == [
        go2rtc_client.HomeKitCamera(
            name="Camera-Hub-G3-AB12",
            url="homekit://192.0.2.10:12345",
        )
    ]
    assert session.calls[1] == (
        "POST",
        "http://go2rtc:1984/api/homekit",
        None,
        {
            "id": "ha_aqara_g3",
            "src": "homekit://192.0.2.10:12345",
            "pin": "123-45-678",
        },
    )


def test_go2rtc_lists_streams_and_fetches_snapshot():
    session = _FakeSession(
        [
            _FakeResponse({"z-camera": {}, "a-camera": {}}),
            _FakeResponse(body=b"jpeg"),
        ]
    )
    client = go2rtc_client.Go2RtcClient(session, "http://go2rtc:1984")

    assert asyncio.run(client.list_streams()) == ["a-camera", "z-camera"]
    assert asyncio.run(client.get_snapshot("a-camera", 640, 480)) == b"jpeg"
    assert session.calls[1][2] == {"src": "a-camera", "width": "640", "height": "480"}
    assert session.calls[1][3] is None
