from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_PATH = ROOT / "custom_components" / "ha_aqara_devices"
PACKAGE = "unload_test_package"


def _module(name: str, **attributes):
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load_integration_module():
    stubs = {
        "voluptuous": _module(
            "voluptuous",
            Required=lambda value: value,
            Schema=lambda value: value,
        ),
        "homeassistant": _module("homeassistant"),
        "homeassistant.config_entries": _module("homeassistant.config_entries", ConfigEntry=object),
        "homeassistant.core": _module(
            "homeassistant.core",
            HomeAssistant=object,
            ServiceCall=object,
            callback=lambda func: func,
        ),
        "homeassistant.exceptions": _module(
            "homeassistant.exceptions",
            ConfigEntryAuthFailed=RuntimeError,
            ConfigEntryNotReady=RuntimeError,
            HomeAssistantError=RuntimeError,
        ),
        "homeassistant.helpers": _module(
            "homeassistant.helpers",
            aiohttp_client=SimpleNamespace(),
            config_validation=SimpleNamespace(
                config_entry_only_config_schema=lambda domain: {},
                string=str,
            ),
            device_registry=SimpleNamespace(),
            entity_registry=SimpleNamespace(),
        ),
        "homeassistant.helpers.update_coordinator": _module(
            "homeassistant.helpers.update_coordinator",
            DataUpdateCoordinator=object,
            UpdateFailed=RuntimeError,
        ),
        "homeassistant.helpers.typing": _module(
            "homeassistant.helpers.typing",
            ConfigType=dict,
        ),
        f"{PACKAGE}.entity_migration": _module(
            f"{PACKAGE}.entity_migration",
            remove_obsolete_g410_entities=lambda *args: None,
        ),
    }
    spec = importlib.util.spec_from_file_location(
        PACKAGE,
        INTEGRATION_PATH / "__init__.py",
        submodule_search_locations=[str(INTEGRATION_PATH)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    stubs[PACKAGE] = module
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


integration = _load_integration_module()


class _ConfigEntries:
    def __init__(self, unload_result: bool, calls: list[str]):
        self._unload_result = unload_result
        self._calls = calls

    async def async_unload_platforms(self, entry, platforms):
        self._calls.append("platforms")
        return self._unload_result


class _BridgeManager:
    def __init__(self, calls: list[str]):
        self._calls = calls

    async def async_stop(self):
        self._calls.append("bridge")


class UnloadLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_platform_unload_keeps_bridge_running(self):
        calls: list[str] = []
        entry = SimpleNamespace(entry_id="entry")
        manager = _BridgeManager(calls)
        hass = SimpleNamespace(
            config_entries=_ConfigEntries(False, calls),
            data={integration.DOMAIN: {entry.entry_id: {"bridge_manager": manager}}},
        )

        result = await integration.async_unload_entry(hass, entry)

        self.assertFalse(result)
        self.assertEqual(calls, ["platforms"])
        self.assertIn(entry.entry_id, hass.data[integration.DOMAIN])

    async def test_successful_platform_unload_stops_bridge_afterward(self):
        calls: list[str] = []
        entry = SimpleNamespace(entry_id="entry")
        manager = _BridgeManager(calls)
        hass = SimpleNamespace(
            config_entries=_ConfigEntries(True, calls),
            data={integration.DOMAIN: {entry.entry_id: {"bridge_manager": manager}}},
        )

        result = await integration.async_unload_entry(hass, entry)

        self.assertTrue(result)
        self.assertEqual(calls, ["platforms", "bridge"])
        self.assertNotIn(entry.entry_id, hass.data[integration.DOMAIN])


if __name__ == "__main__":
    unittest.main()
