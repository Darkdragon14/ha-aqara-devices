from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "u200_api_test_package"


def _load_api_modules():
    package = ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "ha_aqara_devices")]
    homeassistant = ModuleType("homeassistant")
    homeassistant_const = ModuleType("homeassistant.const")
    homeassistant_const.PERCENTAGE = "%"
    homeassistant_const.UnitOfElectricPotential = type(
        "UnitOfElectricPotential",
        (),
        {"VOLT": "V"},
    )
    aiohttp = ModuleType("aiohttp")
    aiohttp.ClientSession = object
    with patch.dict(
        sys.modules,
        {
            PACKAGE: package,
            "homeassistant": homeassistant,
            "homeassistant.const": homeassistant_const,
            "aiohttp": aiohttp,
        },
    ):
        api_module = importlib.import_module(f"{PACKAGE}.api")
        u200_module = importlib.import_module(f"{PACKAGE}.u200")
    return api_module, u200_module


api_module, u200_module = _load_api_modules()


def _complete_trait_items():
    items = []
    for spec in u200_module.U200_STATE_TRAITS:
        value = {
            "bool": True,
            "float": 50,
            "string": "1",
        }[spec["value_type"]]
        items.append(
            {
                "deviceId": "matt.u200",
                "endpointId": spec["endpoint_id"],
                "functionCode": spec["function_code"],
                "traitCode": spec["trait_code"],
                "value": value,
                "code": 0,
            }
        )
    return items


class U200ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_only_subscribable_known_u200_traits(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        api.query_matter_device_config = AsyncMock(
            return_value={
                "code": 0,
                "result": {
                    "data": [
                        {
                            "deviceId": "matt.u200",
                            "endpoints": [
                                {
                                    "endpointId": 2,
                                    "functions": [
                                        {
                                            "functionCode": "DoorLock",
                                            "traits": [
                                                {
                                                    "traitCode": "LockState",
                                                    "parameter": {"subscribable": True},
                                                },
                                                {
                                                    "traitCode": "DoorState",
                                                    "parameter": {"subscribable": False},
                                                },
                                                {
                                                    "traitCode": "Unknown",
                                                    "parameter": {"subscribable": True},
                                                },
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
            }
        )

        paths = await api.get_u200_subscribable_trait_paths(["matt.u200"])

        self.assertEqual(paths, {"matt.u200": {"2.DoorLock.LockState"}})

    async def test_subscribable_trait_discovery_rejects_api_error(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        api.query_matter_device_config = AsyncMock(
            return_value={"code": 500, "message": "failed"}
        )

        with self.assertRaisesRegex(RuntimeError, "trait capabilities"):
            await api.get_u200_subscribable_trait_paths(["matt.u200"])

    async def test_subscribable_trait_discovery_batches_ten_devices(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        api.query_matter_device_config = AsyncMock(
            side_effect=[
                {"code": 0, "result": {"data": []}},
                {"code": 0, "result": {"data": []}},
            ]
        )
        dids = [f"matt.u200.{index}" for index in range(11)]

        await api.get_u200_subscribable_trait_paths(dids)

        self.assertEqual(api.query_matter_device_config.await_count, 2)
        api.query_matter_device_config.assert_any_await(dids[:10])
        api.query_matter_device_config.assert_any_await(dids[10:])

    async def test_u200_state_accepts_missing_optional_trait(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = _complete_trait_items()[:-1]
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        state = await api.get_u200_state("matt.u200")

        self.assertEqual(state["lock_state"], "1")
        self.assertNotIn("door_state", state)

    async def test_u200_state_accepts_optional_trait_error(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = _complete_trait_items()
        items[0]["code"] = 1
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        state = await api.get_u200_state("matt.u200")

        self.assertEqual(state["lock_state"], "1")
        self.assertNotIn("reachable", state)

    async def test_u200_state_rejects_missing_lock_state(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = [
            item for item in _complete_trait_items() if item["traitCode"] != "LockState"
        ]
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "lock_state"):
            await api.get_u200_state("matt.u200")

    async def test_u200_state_rejects_lock_state_error(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = _complete_trait_items()
        lock_state = next(item for item in items if item["traitCode"] == "LockState")
        lock_state["code"] = 1
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "lock_state"):
            await api.get_u200_state("matt.u200")

    def test_subscriptions_use_discovered_subscribable_paths(self):
        subscriptions = u200_module.build_u200_trait_subscriptions(
            [{"did": "matt.u200"}],
            {"matt.u200": {"2.DoorLock.LockState"}},
        )

        self.assertEqual(
            subscriptions,
            [
                {
                    "deviceId": "matt.u200",
                    "codePaths": ["2.DoorLock.LockState"],
                    "attach": "ha_aqara_devices",
                }
            ],
        )

    def test_subscriptions_fall_back_when_device_capabilities_are_missing(self):
        subscriptions = u200_module.build_u200_trait_subscriptions(
            [{"did": "matt.u200"}], {}
        )

        self.assertEqual(
            subscriptions[0]["codePaths"],
            [
                u200_module.u200_trait_code_path(spec)
                for spec in u200_module.U200_STATE_TRAITS
            ],
        )


if __name__ == "__main__":
    unittest.main()
