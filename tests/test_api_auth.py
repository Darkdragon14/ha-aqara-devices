from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_PATH = ROOT / "custom_components" / "ha_aqara_devices"
PACKAGE = "api_auth_test_package"


def _load_api_module():
    package = ModuleType(PACKAGE)
    package.__path__ = [str(INTEGRATION_PATH)]
    aiohttp = ModuleType("aiohttp")
    aiohttp.ClientSession = object
    u200 = ModuleType(f"{PACKAGE}.u200")
    u200.U200_LOCK_ENDPOINT_ID = 1
    u200.U200_LOCK_FUNCTION = "lock"
    u200.U200_LOCK_STATE_LOCKED = "locked"
    u200.U200_STATE_TRAITS = []
    u200.U200_TRAIT_SPEC_MAP = {}
    u200.u200_trait_request = lambda *args: {}
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.api", INTEGRATION_PATH / "api.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = package
    sys.modules[u200.__name__] = u200
    sys.modules[spec.name] = module
    previous_aiohttp = sys.modules.get("aiohttp")
    sys.modules["aiohttp"] = aiohttp
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_aiohttp is None:
            sys.modules.pop("aiohttp", None)
        else:
            sys.modules["aiohttp"] = previous_aiohttp
    return module


api_module = _load_api_module()


class _Response:
    status = 200

    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def text(self):
        return json.dumps(self._data)


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, *, data, headers):
        self.requests.append({"url": url, "data": json.loads(data), "headers": headers})
        return _Response(self.responses.pop(0))


class AqaraAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_code_108_refreshes_retries_and_persists_auth(self):
        session = _Session(
            [
                {"code": 108, "message": "Request failed", "messageDetail": "AccessToken expired"},
                {"code": 0, "result": {"accessToken": "new-access", "expiresIn": "3600"}},
                {"code": 0, "result": {"data": []}},
            ]
        )
        auth_updates = []
        api = api_module.AqaraApi(
            "EU",
            session,
            app_id="app-id",
            app_key="app-key",
            key_id="key-id",
            access_token="old-access",
            refresh_token="refresh-token",
            open_id="open-id",
            auth_updated_callback=auth_updates.append,
        )

        result = await api._open_request("query.device.info", {}, authenticated=True)

        self.assertEqual(result["code"], 0)
        self.assertEqual([request["data"]["intent"] for request in session.requests], [
            "query.device.info",
            "config.auth.refreshToken",
            "query.device.info",
        ])
        self.assertEqual(session.requests[-1]["headers"]["Accesstoken"], "new-access")
        self.assertEqual(auth_updates[-1]["access_token"], "new-access")
        self.assertEqual(auth_updates[-1]["refresh_token"], "refresh-token")
        self.assertEqual(auth_updates[-1]["open_id"], "open-id")

    async def test_code_108_from_refresh_requires_reauthentication(self):
        session = _Session(
            [
                {"code": 108, "messageDetail": "AccessToken expired"},
                {"code": 108, "messageDetail": "RefreshToken expired"},
            ]
        )
        api = api_module.AqaraApi(
            "EU",
            session,
            app_id="app-id",
            app_key="app-key",
            key_id="key-id",
            access_token="old-access",
            refresh_token="expired-refresh",
        )

        with self.assertRaises(api_module.AqaraAuthError):
            await api._open_request("query.device.info", {}, authenticated=True)

    async def test_unrecognized_refresh_failure_requires_reauthentication(self):
        session = _Session([{"code": 500, "message": "Internal service error"}])
        api = api_module.AqaraApi(
            "EU",
            session,
            app_id="app-id",
            app_key="app-key",
            key_id="key-id",
            access_token="old-access",
            refresh_token="refresh-token",
        )

        with self.assertRaises(api_module.AqaraAuthError):
            await api.refresh_access_token(force=True)


if __name__ == "__main__":
    unittest.main()
