from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


ROOT_PATH = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT_PATH
    / "custom_components"
    / "ha_aqara_devices"
    / "child_devices.py"
)
TRANSLATIONS_PATH = ROOT_PATH / "custom_components" / "ha_aqara_devices" / "translations"
SPEC = importlib.util.spec_from_file_location("child_devices_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
child_devices = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(child_devices)


class ChildAccessTests(unittest.TestCase):
    def test_numeric_access_values_follow_aqara_enum(self):
        expected = {
            1: (True, False, False),
            2: (False, False, True),
            3: (True, False, True),
            4: (False, True, False),
            5: (True, True, False),
            6: (False, True, True),
            7: (True, True, True),
        }

        for access, flags in expected.items():
            with self.subTest(access=access):
                self.assertEqual(child_devices._access_flags({"access": access}), flags)

    def test_only_readable_resources_create_specs(self):
        child = {"did": "child.did", "parentDid": "hub.did", "model": "plug.model"}
        resources = [
            {"resourceId": f"resource.{access}", "access": access}
            for access in range(1, 8)
        ]

        specs = child_devices.build_child_entity_specs(
            [child],
            {"plug.model": resources},
        )

        self.assertEqual(
            {spec["resource_id"] for spec in specs},
            {"resource.1", "resource.3", "resource.5", "resource.7"},
        )

    def test_documented_string_enums_create_binary_sensor(self):
        child = {"did": "child.did", "parentDid": "hub.did", "model": "plug.model"}

        specs = child_devices.build_child_entity_specs(
            [child],
            {
                "plug.model": [
                    {
                        "resourceId": "4.1.85",
                        "access": 3,
                        "enums": "0,1",
                    }
                ]
            },
        )

        self.assertEqual(specs[0]["platform"], "binary_sensor")
        self.assertEqual(specs[0]["value_type"], "bool")

    def test_numeric_aqara_unit_identifier_is_not_exposed_as_native_unit(self):
        child = {"did": "child.did", "parentDid": "hub.did", "model": "sensor.model"}

        specs = child_devices.build_child_entity_specs(
            [child],
            {
                "sensor.model": [
                    {
                        "resourceId": "0.1.85",
                        "access": 3,
                        "unit": 1,
                    }
                ]
            },
        )

        self.assertIsNone(specs[0]["unit"])

    def test_smoke_sensor_resources_receive_translation_keys(self):
        child = {
            "did": "smoke.did",
            "parentDid": "hub.did",
            "model": "lumi.sensor_smoke.acn03",
        }
        resources = [
            {"resourceId": "4.12.85", "name": "消音", "enums": "0,1"},
            {"resourceId": "4.15.85", "name": "自检", "enums": "0,1"},
            {"resourceId": "8.0.2008", "name": "电池电压值"},
            {"resourceId": "8.0.2007", "name": "Zigbee信号强度"},
            {"resourceId": "8.0.2232", "name": "设备报警", "enums": "0,1"},
            {"resourceId": "8.0.2234", "name": "故障报警", "enums": "0,1"},
            {"resourceId": "8.0.9001", "name": "低电压报警"},
            {"resourceId": "unknown.heartbeat", "name": "Heartbeat Indicator Light"},
        ]

        specs = child_devices.build_child_entity_specs(
            [child],
            {"lumi.sensor_smoke.acn03": resources},
        )

        expected = {
            "4.12.85": ("binary_sensor", "smoke_manual_mute"),
            "4.15.85": ("binary_sensor", "smoke_self_test"),
            "8.0.2008": ("sensor", "battery_voltage"),
            "8.0.2007": ("sensor", "zigbee_signal_strength"),
            "8.0.2232": ("binary_sensor", "smoke_alarm"),
            "8.0.2234": ("binary_sensor", "smoke_fault_alarm"),
            "8.0.9001": ("sensor", "low_battery_alarm"),
            "unknown.heartbeat": ("sensor", "heartbeat_indicator"),
        }
        self.assertEqual(
            {
                spec["resource_id"]: (spec["platform"], spec.get("translation_key"))
                for spec in specs
            },
            expected,
        )

        for translation_path in TRANSLATIONS_PATH.glob("*.json"):
            translations = json.loads(translation_path.read_text())
            for platform, translation_key in expected.values():
                with self.subTest(
                    translation=translation_path.name,
                    platform=platform,
                    translation_key=translation_key,
                ):
                    self.assertIn(translation_key, translations["entity"][platform])
            with self.subTest(
                translation=translation_path.name,
                translation_key="low_battery_alarm",
            ):
                self.assertIn("low_battery_alarm", translations["entity"]["sensor"])
                self.assertIn(
                    "low_battery_alarm",
                    translations["entity"]["binary_sensor"],
                )

    def test_battery_level_resource_is_not_mislabeled_as_voltage(self):
        child = {
            "did": "smoke.did",
            "parentDid": "hub.did",
            "model": "lumi.sensor_smoke.acn03",
        }

        specs = child_devices.build_child_entity_specs(
            [child],
            {
                "lumi.sensor_smoke.acn03": [
                    {"resourceId": "8.0.2001", "name": "Battery Level"}
                ]
            },
        )

        self.assertNotIn("translation_key", specs[0])

    def test_smoke_sensor_chinese_name_fallbacks(self):
        child = {
            "did": "smoke.did",
            "parentDid": "hub.did",
            "model": "lumi.sensor_smoke.acn03",
        }
        expected = {
            "Heartbeat Indicator Light": "heartbeat_indicator",
            "Zigbee信号强度": "zigbee_signal_strength",
            "低电压报警": "low_battery_alarm",
            "故障报警": "smoke_fault_alarm",
            "消音": "smoke_manual_mute",
            "电池电压值": "battery_voltage",
            "自检": "smoke_self_test",
            "设备报警": "smoke_alarm",
        }

        for index, (resource_name, translation_key) in enumerate(expected.items()):
            with self.subTest(resource_name=resource_name):
                specs = child_devices.build_child_entity_specs(
                    [child],
                    {
                        "lumi.sensor_smoke.acn03": [
                            {
                                "resourceId": f"unknown.{index}",
                                "name": resource_name,
                            }
                        ]
                    },
                )

                self.assertEqual(specs[0].get("translation_key"), translation_key)

    def test_smoke_translation_mapping_is_model_specific(self):
        child = {"did": "other.did", "parentDid": "hub.did", "model": "other.model"}

        specs = child_devices.build_child_entity_specs(
            [child],
            {"other.model": [{"resourceId": "4.12.85", "name": "消音"}]},
        )

        self.assertNotIn("translation_key", specs[0])


class ChildSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.specs = [
            {
                "did": "child.did",
                "resource_id": "state.reported",
                "unique_id": "reported",
                "reportable": True,
                "enabled_default": True,
            },
            {
                "did": "child.did",
                "resource_id": "state.polled",
                "unique_id": "polled",
                "reportable": False,
                "enabled_default": True,
            },
        ]

    def test_only_reportable_enabled_resources_are_subscribed(self):
        subscriptions = child_devices.build_child_active_subscriptions(
            {"reported", "polled"},
            self.specs,
        )

        self.assertEqual(
            subscriptions,
            [
                {
                    "subjectId": "child.did",
                    "resourceIds": ["state.reported"],
                    "attach": "ha_aqara_devices",
                }
            ],
        )

    def test_non_reportable_enabled_resource_requires_polling(self):
        self.assertEqual(
            child_devices.child_polling_required_dids({"reported", "polled"}, self.specs),
            {"child.did"},
        )
        self.assertEqual(
            child_devices.child_polling_required_dids({"reported"}, self.specs),
            set(),
        )

    def test_new_default_enabled_resources_are_selected_before_registry_creation(self):
        subscriptions = child_devices.build_child_active_subscriptions(
            set(),
            self.specs,
            known_unique_ids=set(),
        )

        self.assertEqual(subscriptions[0]["resourceIds"], ["state.reported"])
        self.assertEqual(
            child_devices.child_polling_required_dids(
                set(),
                self.specs,
                known_unique_ids=set(),
            ),
            {"child.did"},
        )


if __name__ == "__main__":
    unittest.main()
