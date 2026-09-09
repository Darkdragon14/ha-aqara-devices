from __future__ import annotations

import asyncio
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
    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, *, name, update_method, update_interval):
            self.name = name
            self.update_method = update_method
            self.update_interval = update_interval

        async def async_refresh(self):
            return await self.update_method()

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
            DataUpdateCoordinator=_DataUpdateCoordinator,
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
    async def test_push_during_failed_poll_keeps_failure_count_reset(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def fetch():
            started.set()
            await release.wait()
            raise RuntimeError("temporary failure")

        class _Hass:
            @staticmethod
            def async_create_task(coroutine):
                coroutine.close()

        with patch.dict(
            sys.modules,
            {
                f"{PACKAGE}.api": _module(
                    f"{PACKAGE}.api",
                    AqaraAuthError=type("AqaraAuthError", (Exception,), {}),
                )
            },
        ):
            coordinator = integration._create_resilient_coordinator(
                _Hass(),
                "matt.u200",
                "u200-lock-state",
                fetch,
                30,
                3,
            )

        coordinator._aqara_resilient_state.update(
            {
                "last_data": {"lock_state": "1"},
                "failures": 2,
            }
        )
        push_versions = coordinator._aqara_push_version_data
        in_flight_poll = asyncio.create_task(coordinator.update_method())
        await started.wait()

        coordinator._aqara_resilient_state.update(
            {
                "last_data": {"lock_state": "2"},
                "failures": 0,
            }
        )
        push_versions["lock_state"] = (1, "2")
        release.set()

        self.assertEqual(await in_flight_poll, {"lock_state": "2"})
        self.assertEqual(coordinator._aqara_resilient_state["failures"], 0)

    async def test_push_reset_keeps_recent_state_on_first_failed_fallback_poll(self):
        async def fetch():
            raise RuntimeError("temporary failure")

        class _Hass:
            @staticmethod
            def async_create_task(coroutine):
                coroutine.close()

        with patch.dict(
            sys.modules,
            {
                f"{PACKAGE}.api": _module(
                    f"{PACKAGE}.api",
                    AqaraAuthError=type("AqaraAuthError", (Exception,), {}),
                )
            },
        ):
            coordinator = integration._create_resilient_coordinator(
                _Hass(),
                "matt.u200",
                "u200-lock-state",
                fetch,
                30,
                3,
            )

        coordinator._aqara_resilient_state.update(
            {
                "last_data": {"lock_state": "2"},
                "failures": 0,
            }
        )

        self.assertEqual(await coordinator.update_method(), {"lock_state": "2"})
        self.assertEqual(coordinator._aqara_resilient_state["failures"], 1)
        self.assertEqual(coordinator._aqara_resilient_state["network_attempts"], 1)
        self.assertFalse(coordinator._aqara_resilient_state["last_network_success"])

    async def test_coordinator_overlays_only_pushes_received_during_poll(self):
        started = asyncio.Event()
        release = asyncio.Event()
        poll_results = [
            {"lock_state": "1", "battery_percentage": 64.0},
            {"lock_state": "3", "battery_percentage": 65.0},
        ]

        async def fetch():
            if len(poll_results) == 2:
                started.set()
                await release.wait()
            return poll_results.pop(0)

        class _Hass:
            @staticmethod
            def async_create_task(coroutine):
                coroutine.close()

        with patch.dict(
            sys.modules,
            {f"{PACKAGE}.api": _module(f"{PACKAGE}.api", AqaraAuthError=RuntimeError)},
        ):
            coordinator = integration._create_resilient_coordinator(
                _Hass(),
                "matt.u200",
                "u200-lock-state",
                fetch,
                30,
                3,
            )
        push_versions = {}
        coordinator._aqara_push_versions = lambda: dict(push_versions)

        in_flight_poll = asyncio.create_task(coordinator.update_method())
        await started.wait()
        push_versions["lock_state"] = (1, "2")
        release.set()

        self.assertEqual(
            await in_flight_poll,
            {"lock_state": "2", "battery_percentage": 64.0},
        )
        self.assertEqual(
            await coordinator.update_method(),
            {"lock_state": "3", "battery_percentage": 65.0},
        )

    async def test_disconnected_poll_applies_push_received_after_reconnect(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def fetch():
            started.set()
            await release.wait()
            return {"lock_state": "1"}

        class _Hass:
            @staticmethod
            def async_create_task(coroutine):
                coroutine.close()

        with patch.dict(
            sys.modules,
            {f"{PACKAGE}.api": _module(f"{PACKAGE}.api", AqaraAuthError=RuntimeError)},
        ):
            coordinator = integration._create_resilient_coordinator(
                _Hass(),
                "matt.u200",
                "u200-lock-state",
                fetch,
                30,
                3,
            )

        push_versions = coordinator._aqara_push_version_data
        in_flight_poll = asyncio.create_task(coordinator.update_method())
        await started.wait()
        push_versions["lock_state"] = (1, "2")
        release.set()

        self.assertEqual(await in_flight_poll, {"lock_state": "2"})

    async def test_poll_crossing_disconnect_reconnect_applies_later_push(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def fetch():
            started.set()
            await release.wait()
            return {"lock_state": "1"}

        class _Hass:
            @staticmethod
            def async_create_task(coroutine):
                coroutine.close()

        with patch.dict(
            sys.modules,
            {f"{PACKAGE}.api": _module(f"{PACKAGE}.api", AqaraAuthError=RuntimeError)},
        ):
            coordinator = integration._create_resilient_coordinator(
                _Hass(),
                "matt.u200",
                "u200-lock-state",
                fetch,
                30,
                3,
            )

        provider = coordinator._aqara_push_versions
        push_versions = coordinator._aqara_push_version_data
        in_flight_poll = asyncio.create_task(coordinator.update_method())
        await started.wait()
        # Disconnect and reconnect leave the stable provider unchanged.
        self.assertIs(coordinator._aqara_push_versions, provider)
        push_versions["lock_state"] = (1, "2")
        release.set()

        self.assertEqual(await in_flight_poll, {"lock_state": "2"})

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
