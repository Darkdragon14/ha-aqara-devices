from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ha_aqara_devices"
PACKAGE = "matter_diagnostics_test_package"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", INTEGRATION / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package = ModuleType(PACKAGE)
package.__path__ = [str(INTEGRATION)]
sys.modules[PACKAGE] = package
capabilities = _load("matter_lock_diagnostics")
stubs = {}
for name, attribute in (("homeassistant.config_entries", "ConfigEntry"), ("homeassistant.core", "HomeAssistant")):
    stubs[name] = ModuleType(name)
    setattr(stubs[name], attribute, object)
with patch.dict(sys.modules, stubs):
    diagnostics = _load("diagnostics")

MODEL = "aqara.matter.4447_10244"


def _response():
    return {
        "code": 0, "accessToken": "SECRET_TOKEN", "message": "SECRET_ERROR",
        "result": {"data": [{
            "model": MODEL, "deviceId": "PRIVATE_DID", "deviceName": "PRIVATE_NAME",
            "endpoints": [{"endpointId": 2, "functions": [{
                "functionCode": "DoorLock", "traits": [{
                    "traitCode": "LockOperation", "traitId": 33139,
                    "value": "PRIVATE_CREDENTIAL", "parameter": {
                        "type": "Struct", "readable": False, "writable": False,
                        "subscribable": True, "defaultValue": "PRIVATE_PIN",
                        "supportedValues": [{"key": "PRIVATE_USER", "value": "PRIVATE_PIN"}],
                    },
                }],
            }]}],
        }]},
    }


class SanitizerTests(unittest.TestCase):
    def test_only_allowlisted_metadata_is_returned(self):
        result = capabilities.sanitize_capabilities(_response(), MODEL)
        self.assertEqual(result, {"status": "success", "endpoints": [{
            "endpointId": 2, "functions": [{"functionCode": "DoorLock", "traits": [{
                "traitCode": "LockOperation", "traitId": 33139, "type": "Struct",
                "readable": False, "writable": False, "subscribable": True,
            }]}],
        }]})
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("SECRET", json.dumps(result))

    def test_errors_and_missing_data_are_safe(self):
        for raw, status in (
            (None, "invalid_response"),
            ({"code": "PRIVATE_PIN", "message": "SECRET"}, "api_error"),
            ({"code": 0}, "no_capabilities"),
            ({"code": 0, "result": {"data": "PRIVATE"}}, "no_capabilities"),
        ):
            self.assertEqual(capabilities.sanitize_capabilities(raw, MODEL)["status"], status)

    def test_wrong_model_and_malformed_metadata_are_ignored(self):
        raw = _response()
        self.assertEqual(capabilities.sanitize_capabilities(raw, "other")["status"], "no_capabilities")
        endpoint = raw["result"]["data"][0]["endpoints"][0]
        endpoint["functions"].extend([None, {"functionCode": "PRIVATE TOKEN", "traits": []}])
        trait = endpoint["functions"][0]["traits"][0]
        trait["parameter"] = {"type": {"secret": "PRIVATE"}, "readable": "PRIVATE"}
        result = capabilities.sanitize_capabilities(raw, MODEL)
        self.assertEqual(result["endpoints"][0]["functions"][0]["traits"], [
            {"traitCode": "LockOperation", "traitId": 33139},
        ])
        endpoint["endpointId"] = True
        self.assertEqual(capabilities.sanitize_capabilities(raw, MODEL)["status"], "no_capabilities")


class CollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_collection_skips_u200_and_retains_no_identifiers(self):
        api = SimpleNamespace(query_matter_device_config=AsyncMock(return_value=_response()))
        cache = []
        await capabilities.collect_lock_capabilities(api, [
            {"did": "u200", "model": "aqara.matter.4447_10242"},
            {"did": "PRIVATE_DID", "model": MODEL},
        ], cache)
        api.query_matter_device_config.assert_awaited_once_with(["PRIVATE_DID"])
        self.assertEqual(cache[0]["status"], "success")
        self.assertNotIn("PRIVATE", json.dumps(cache))

    async def test_failed_lock_does_not_prevent_next_collection(self):
        api = SimpleNamespace(query_matter_device_config=AsyncMock(
            side_effect=[RuntimeError("SECRET_TOKEN"), _response()],
        ))
        cache = []
        await capabilities.collect_lock_capabilities(api, [
            {"did": "first", "model": "aqara.matter.4447_10241"},
            {"did": "second", "model": MODEL},
        ], cache)
        self.assertEqual([item["status"] for item in cache], ["request_failed", "success"])
        self.assertNotIn("SECRET", json.dumps(cache))

    async def test_timeout_is_bounded_and_sanitized(self):
        async def never_returns(_dids):
            await asyncio.Event().wait()

        cache = []
        with patch.object(capabilities, "CAPABILITY_TIMEOUT_SECONDS", 0.001):
            await capabilities.collect_lock_capabilities(
                SimpleNamespace(query_matter_device_config=never_returns),
                [{"did": "private", "model": MODEL}], cache,
            )
        self.assertEqual(cache, [{"model": MODEL, "status": "timeout"}])

    async def test_cancellation_propagates(self):
        api = SimpleNamespace(query_matter_device_config=AsyncMock(side_effect=asyncio.CancelledError))
        with self.assertRaises(asyncio.CancelledError):
            await capabilities.collect_lock_capabilities(api, [{"did": "private", "model": MODEL}], [])

    async def test_download_does_not_include_config_or_coordinator_data(self):
        entry = SimpleNamespace(entry_id="entry", data={"access_token": "SECRET"})
        cache = [{"model": MODEL, "status": "pending"}]
        hass = SimpleNamespace(data={diagnostics.DOMAIN: {
            "entry": {"matter_lock_capabilities": cache, "api": "SECRET", "u200_coordinators": "PRIVATE"},
        }})
        result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
        self.assertEqual(result, {"matter_lock_capabilities": cache})
        result["matter_lock_capabilities"][0]["status"] = "changed"
        self.assertEqual(cache[0]["status"], "pending")
        self.assertEqual(await diagnostics.async_get_config_entry_diagnostics(hass, SimpleNamespace(entry_id="missing")),
                         {"matter_lock_capabilities": []})
