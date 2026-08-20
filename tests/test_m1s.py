from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.ha_aqara_devices"


class _EnumLikeMeta(type):
    def __getattr__(cls, name):
        return name.lower()

    def __call__(cls, value):
        return value


class _EnumLike(metaclass=_EnumLikeMeta):
    pass


class _ColorMode:
    RGB = "rgb"


class _Entity:
    def async_write_ha_state(self):
        return None


class _CoordinatorEntity(_Entity):
    def __init__(self, coordinator):
        self.coordinator = coordinator


def _module(name: str, **attributes):
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _import_test_modules():
    stubs: dict[str, ModuleType] = {}

    def stub(name: str, **attributes):
        module = _module(name, **attributes)
        stubs[name] = module
        return module

    custom_components = stub("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    package = stub(PACKAGE)
    package.__path__ = [str(ROOT / "custom_components" / "ha_aqara_devices")]

    stub("aiohttp", ClientSession=object, ClientTimeout=object)
    stub("homeassistant")
    stub("homeassistant.components")
    stub(
        "homeassistant.components.binary_sensor",
        BinarySensorDeviceClass=_EnumLike,
    )
    stub(
        "homeassistant.components.sensor",
        SensorDeviceClass=_EnumLike,
        SensorStateClass=_EnumLike,
    )
    stub(
        "homeassistant.components.light",
        ATTR_BRIGHTNESS="brightness",
        ATTR_RGB_COLOR="rgb_color",
        ColorMode=_ColorMode,
        LightEntity=_Entity,
    )
    stub("homeassistant.components.number", NumberEntity=_Entity)
    stub("homeassistant.config_entries", ConfigEntry=object)
    stub(
        "homeassistant.const",
        PERCENTAGE="%",
        UnitOfTemperature=_EnumLike,
    )
    stub("homeassistant.core", HomeAssistant=object)
    stub("homeassistant.helpers")
    stub(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=_CoordinatorEntity,
        DataUpdateCoordinator=object,
    )
    stub("homeassistant.util")
    stub(
        "homeassistant.util.color",
        brightness_to_value=lambda scale, value: (
            scale[0] + (value - 1) * (scale[1] - scale[0]) / 254
        ),
        value_to_brightness=lambda scale, value: round(
            1 + (value - scale[0]) * 254 / (scale[1] - scale[0])
        ),
    )

    class AqaraAuthError(RuntimeError):
        pass

    stub(f"{PACKAGE}.api", AqaraApi=object, AqaraAuthError=AqaraAuthError)
    stub(f"{PACKAGE}.device_info", build_device_info=lambda *args: {})

    with patch.dict(sys.modules, stubs):
        for name in tuple(sys.modules):
            if name.startswith(f"{PACKAGE}.") and name not in stubs:
                sys.modules.pop(name)
        modules = (
            importlib.import_module(f"{PACKAGE}.bridge_specs"),
            importlib.import_module(f"{PACKAGE}.light"),
            importlib.import_module(f"{PACKAGE}.number"),
            importlib.import_module(f"{PACKAGE}.push"),
        )
    return modules


bridge_specs, light_module, number_module, push_module = _import_test_modules()

M1S_MODEL = "lumi.gateway.aeu01"
M1S_GEN2_MODEL = "lumi.gateway.agl002"
M1S_COMMON_RESOURCES = {
    "8.0.2026",
    "14.1.85",
    "14.1.111",
    "14.1.1000",
    "14.7.85",
    "14.7.111",
    "14.7.1006",
    "14.11.85",
}
M1S_ORIGINAL_RESOURCES = {
    "14.1.113",
    "14.2.85",
    "14.3.111",
    "14.3.113",
    "14.3.1000",
}


class _Coordinator:
    name = "m1s-state"

    def __init__(self, data=None):
        self.data = data or {}
        self.updates = []
        self.refreshes = 0

    def async_set_updated_data(self, data):
        self.data = data
        self.updates.append(data)

    async def async_request_refresh(self):
        self.refreshes += 1


class M1SSpecTests(unittest.TestCase):
    def test_resources_are_filtered_by_model(self):
        original = set(bridge_specs.m1s_resource_spec_map_for_model(M1S_MODEL))
        gen2 = set(bridge_specs.m1s_resource_spec_map_for_model(M1S_GEN2_MODEL))

        self.assertEqual(M1S_COMMON_RESOURCES | M1S_ORIGINAL_RESOURCES, original)
        self.assertEqual(M1S_COMMON_RESOURCES, gen2)
        self.assertNotIn("14.3.85", original)

    def test_wifi_rssi_converts_unsigned_uint32_to_signed_dbm(self):
        spec = bridge_specs.m1s_resource_spec_map_for_model(M1S_MODEL)["8.0.2026"]

        self.assertEqual(-60, bridge_specs.coerce_spec_value(spec, -60, apply_scale=True))
        self.assertEqual(
            -60,
            bridge_specs.coerce_spec_value(spec, 4294967236, apply_scale=True),
        )
        self.assertIsNone(
            bridge_specs.coerce_spec_value(spec, "invalid", apply_scale=True)
        )

    def test_subscriptions_group_light_and_filter_original_resources(self):
        enabled = {
            "original_night_light",
            "original_device_wifi_rssi",
            "original_system_volume",
            "original_alarm_bell_volume",
            "original_alarm_bell_index",
            "original_alarm_status",
            "original_doorbell_bell_index",
            "original_music_volume",
            "original_music_time_length",
            "original_alarm_time_length",
            "original_music_status",
            "gen2_night_light",
            "gen2_device_wifi_rssi",
            "gen2_system_volume",
            "gen2_alarm_bell_volume",
            "gen2_alarm_bell_index",
            "gen2_alarm_status",
        }

        subscriptions = bridge_specs.build_active_subscriptions(
            enabled,
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
            hubs_m1s=[
                {"did": "original", "model": M1S_MODEL},
                {"did": "gen2", "model": M1S_GEN2_MODEL},
            ],
        )

        self.assertEqual(["original", "gen2"], [item["subjectId"] for item in subscriptions])
        self.assertEqual(
            M1S_COMMON_RESOURCES | M1S_ORIGINAL_RESOURCES,
            set(subscriptions[0]["resourceIds"]),
        )
        self.assertEqual(M1S_COMMON_RESOURCES, set(subscriptions[1]["resourceIds"]))


class M1SLightTests(unittest.IsolatedAsyncioTestCase):
    def _entity(self, data=None):
        coordinator = _Coordinator(data)
        api = SimpleNamespace(res_write=AsyncMock(return_value={"code": 0}))
        entity = light_module.AqaraM1SNightLight(
            coordinator,
            api,
            "m1s",
            "Hall hub",
            M1S_MODEL,
        )
        return entity, coordinator, api

    async def test_decodes_and_writes_brightness_and_rgb(self):
        entity, coordinator, api = self._entity(
            {
                "corridor_light_status": 1,
                "brightness_level": 40,
                "argb_value": 0x28112233,
            }
        )

        self.assertTrue(entity.is_on)
        self.assertEqual(101, entity.brightness)
        self.assertEqual((0x11, 0x22, 0x33), entity.rgb_color)

        await entity.async_turn_on(brightness=128, rgb_color=(1, 2, 3))

        api.res_write.assert_awaited_once_with(
            {
                "subjectId": "m1s",
                "data": {
                    "14.7.111": 1,
                    "14.7.1006": 50,
                    "14.7.85": 0x32010203,
                },
            }
        )
        self.assertEqual(1, coordinator.refreshes)


    async def test_plain_turn_on_restores_default_brightness(self):
        entity, coordinator, api = self._entity(
            {
                "corridor_light_status": 0,
                "brightness_level": 0,
                "argb_value": 0,
            }
        )

        await entity.async_turn_on()

        api.res_write.assert_awaited_once_with(
            {
                "subjectId": "m1s",
                "data": {
                    "14.7.111": 1,
                    "14.7.1006": 100,
                },
            }
        )
        self.assertEqual(1, coordinator.refreshes)


class M1SNumberTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_write_restores_previous_value(self):
        coordinator = _Coordinator({"system_volume": 20})
        api = SimpleNamespace(res_write=AsyncMock(return_value={"code": 1}))
        spec = next(
            spec
            for spec in bridge_specs.m1s_state_specs_for_model(M1S_MODEL)
            if spec["inApp"] == "system_volume"
        )
        entity = number_module.AqaraNumber(
            coordinator,
            api,
            "m1s",
            "Hall hub",
            spec,
            M1S_MODEL,
            "Aqara Hub M1S",
        )
        entity._native_value = 20

        with self.assertRaisesRegex(RuntimeError, "Aqara API error"):
            await entity.async_set_native_value(50)

        self.assertEqual(20, entity.native_value)
        self.assertEqual(0, coordinator.refreshes)

    async def test_write_exception_restores_previous_value(self):
        coordinator = _Coordinator({"system_volume": 20})
        api = SimpleNamespace(res_write=AsyncMock(side_effect=RuntimeError("offline")))
        spec = next(
            spec
            for spec in bridge_specs.m1s_state_specs_for_model(M1S_MODEL)
            if spec["inApp"] == "system_volume"
        )
        entity = number_module.AqaraNumber(
            coordinator,
            api,
            "m1s",
            "Hall hub",
            spec,
            M1S_MODEL,
            "Aqara Hub M1S",
        )
        entity._native_value = 20

        with self.assertRaisesRegex(RuntimeError, "offline"):
            await entity.async_set_native_value(50)

        self.assertEqual(20, entity.native_value)
        self.assertEqual(0, coordinator.refreshes)


class M1SPushTests(unittest.TestCase):
    def test_push_updates_m1s_coordinator(self):
        coordinator = _Coordinator()
        manager = push_module.AqaraBridgePushManager.__new__(
            push_module.AqaraBridgePushManager
        )
        manager._event_id = 0
        manager._seen_event_ids = {}
        manager._cameras = {}
        manager._g2h_pro_cameras = {}
        manager._g410_doorbells = {}
        manager._g4_doorbells = {}
        manager._hubs_m1s = {"m1s": {"did": "m1s", "model": M1S_GEN2_MODEL}}
        manager._hubs_m3 = {}
        manager._hubs_m100 = {}
        manager._hubs_m200 = {}
        manager._a100_pro_locks = {}
        manager._acn002_locks = {}
        manager._child_devices = {}
        manager._presence_devices = {}
        manager._m1s_coordinators = {"m1s": coordinator}
        manager._m1s_state = {"m1s": {}}

        manager._apply_events(
            "batch",
            [{"subjectId": "m1s", "resourceId": "8.0.2026", "value": 4294967236}],
        )

        self.assertEqual(-60, coordinator.data["device_wifi_rssi"])
        self.assertEqual(1, len(coordinator.updates))


if __name__ == "__main__":
    unittest.main()
