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
    async def test_u200_state_rejects_missing_trait(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = _complete_trait_items()[:-1]
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "door_state"):
            await api.get_u200_state("matt.u200")

    async def test_u200_state_rejects_individual_trait_error(self):
        api = api_module.AqaraApi.__new__(api_module.AqaraApi)
        items = _complete_trait_items()
        items[0]["code"] = 1
        api.query_traits = AsyncMock(return_value={"code": 0, "result": items})
        api.query_matter_device_config = AsyncMock()

        with self.assertRaisesRegex(RuntimeError, "reachable"):
            await api.get_u200_state("matt.u200")


if __name__ == "__main__":
    unittest.main()
