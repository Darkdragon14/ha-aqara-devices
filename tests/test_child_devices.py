from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_aqara_devices"
    / "child_devices.py"
)
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
