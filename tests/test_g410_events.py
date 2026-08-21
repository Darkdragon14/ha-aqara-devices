from __future__ import annotations

import importlib
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "custom_components.ha_aqara_devices"


class _EnumLikeMeta(type):
    def __getattr__(cls, name):
        return name.lower()

    def __call__(cls, value):
        return value


class _EnumLike(metaclass=_EnumLikeMeta):
    pass


class _Entity:
    def async_write_ha_state(self):
        self._write_count = getattr(self, "_write_count", 0) + 1


class _EventEntity(_Entity):
    def _trigger_event(self, event_type, event_attributes=None):
        events = getattr(self, "_triggered_events", [])
        events.append((event_type, event_attributes or {}))
        self._triggered_events = events


class _CoordinatorEntity(_Entity):
    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def async_added_to_hass(self):
        return None

    async def async_will_remove_from_hass(self):
        return None

    def _handle_coordinator_update(self):
        return None


def _module(name: str, **attributes):
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _import_test_modules():
    stubs = {}

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
        BinarySensorEntity=_Entity,
    )
    stub(
        "homeassistant.components.sensor",
        SensorDeviceClass=_EnumLike,
        SensorEntity=_Entity,
        SensorStateClass=_EnumLike,
    )
    stub("homeassistant.components.event", EventEntity=_EventEntity)
    stub("homeassistant.config_entries", ConfigEntry=object)
    stub(
        "homeassistant.const",
        PERCENTAGE="%",
        UnitOfTemperature=_EnumLike,
    )
    stub("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    helpers = stub("homeassistant.helpers")
    entity_registry = stub(
        "homeassistant.helpers.entity_registry",
        async_entries_for_config_entry=lambda *args: [],
        async_get=lambda *args: None,
    )
    helpers.entity_registry = entity_registry
    stub("homeassistant.helpers.event", async_call_later=lambda *args: lambda: None)
    stub(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=_CoordinatorEntity,
        DataUpdateCoordinator=object,
    )

    class AqaraAuthError(RuntimeError):
        pass

    stub(f"{PACKAGE}.api", AqaraApi=object, AqaraAuthError=AqaraAuthError)
    stub(
        f"{PACKAGE}.device_info",
        build_child_device_info=lambda *args: {},
        build_device_info=lambda *args: {},
    )
    stub(f"{PACKAGE}.u200", U200_BINARY_SENSORS_DEF=[], U200_SENSORS_DEF=[])

    with patch.dict(sys.modules, stubs):
        for name in tuple(sys.modules):
            if name.startswith(f"{PACKAGE}.") and name not in stubs:
                sys.modules.pop(name)
        modules = (
            importlib.import_module(f"{PACKAGE}.bridge_specs"),
            importlib.import_module(f"{PACKAGE}.binary_sensor"),
            importlib.import_module(f"{PACKAGE}.push"),
            importlib.import_module(f"{PACKAGE}.sensor"),
            importlib.import_module(f"{PACKAGE}.event"),
            importlib.import_module(f"{PACKAGE}.binary_sensors"),
            importlib.import_module(f"{PACKAGE}.sensors"),
            importlib.import_module(f"{PACKAGE}.events"),
            importlib.import_module(f"{PACKAGE}.entity_migration"),
        )
    return modules


(
    bridge_specs,
    binary_sensor_module,
    push_module,
    sensor_module,
    event_module,
    binary_sensors,
    sensors,
    events,
    entity_migration,
) = _import_test_modules()


class _Coordinator:
    name = "g410-state"
    update_interval = None

    def __init__(self):
        self.data = {}
        self.updates = []
        self.refresh_requests = 0

    def async_set_updated_data(self, data):
        self.data = data
        self.updates.append(data)

    async def async_request_refresh(self):
        self.refresh_requests += 1


class _Hass:
    @staticmethod
    def async_create_task(coro):
        asyncio.run(coro)


def _manager(coordinator: _Coordinator, model: str = "lumi.camera.agl006"):
    manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
    manager._event_id = 0
    manager._seen_event_ids = {}
    manager._cameras = {}
    manager._g2h_pro_cameras = {}
    manager._g410_doorbells = {"g410": {"did": "g410", "model": model}}
    manager._g4_doorbells = {}
    manager._hubs_m3 = {}
    manager._hubs_m100 = {}
    manager._hubs_m200 = {}
    manager._a100_pro_locks = {}
    manager._acn002_locks = {}
    manager._presence_devices = {}
    manager._g410_coordinators = {"g410": coordinator}
    manager._g410_state = {"g410": {}}
    return manager


class PushPollingTests(unittest.TestCase):
    def test_sse_only_keeps_polling_for_non_reportable_children(self):
        manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
        standard = _Coordinator()
        polled_child = _Coordinator()
        pushed_child = _Coordinator()
        manager._camera_coordinators = {"standard": standard}
        manager._g2h_pro_coordinators = {}
        manager._g410_coordinators = {}
        manager._g4_coordinators = {}
        manager._m3_coordinators = {}
        manager._m100_coordinators = {}
        manager._m200_coordinators = {}
        manager._a100_pro_coordinators = {}
        manager._acn002_coordinators = {}
        manager._presence_coordinators = {}
        manager._child_coordinators = {
            "polled": polled_child,
            "pushed": pushed_child,
        }
        manager._child_polling_dids = {"polled"}
        manager._sse_connected = None
        manager._hass = _Hass()

        manager._set_sse_connected(True)

        self.assertIsNone(standard.update_interval)
        self.assertEqual(polled_child.update_interval.total_seconds(), 300)
        self.assertIsNone(pushed_child.update_interval)

        manager._set_sse_connected(False)

        self.assertEqual(standard.update_interval.total_seconds(), 300)
        self.assertEqual(pushed_child.update_interval.total_seconds(), 300)
        self.assertEqual(standard.refresh_requests, 1)
        self.assertEqual(pushed_child.refresh_requests, 1)

    def test_subscription_normalization_preserves_attach(self):
        subscriptions = push_module.AqaraBridgePushManager._normalize_subscriptions(
            [
                {
                    "subjectId": "child.did",
                    "resourceIds": ["3.1.85"],
                    "attach": "ha_aqara_devices",
                },
                {
                    "subjectId": "child.did",
                    "resourceIds": ["4.1.85"],
                },
            ]
        )

        self.assertEqual(
            subscriptions,
            [
                {
                    "subjectId": "child.did",
                    "resourceIds": ["3.1.85", "4.1.85"],
                    "attach": "ha_aqara_devices",
                }
            ],
        )

    def test_push_merges_into_latest_polled_coordinator_state(self):
        manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
        coordinator = _Coordinator()
        coordinator.data = {"reported": "old", "polled": "current"}

        state = manager._base_state(
            "batch",
            ("device", "child.did", coordinator.name),
            {"reported": "old", "polled": "stale"},
            coordinator,
            {},
        )

        self.assertEqual(state, {"reported": "old", "polled": "current"})

    def test_push_preserves_cached_state_omitted_from_partial_poll(self):
        manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
        coordinator = _Coordinator()
        coordinator.data = {"polled": "current"}

        state = manager._base_state(
            "batch",
            ("device", "child.did", coordinator.name),
            {"reported": "cached", "polled": "stale"},
            coordinator,
            {},
        )

        self.assertEqual(state, {"reported": "cached", "polled": "current"})


class PushLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_listener_shutdown_does_not_restart_polling(self):
        manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
        manager._stop_event = asyncio.Event()
        manager._connected_event = asyncio.Event()
        manager._set_sse_connected = Mock()

        async def _stop_stream():
            manager._stop_event.set()

        manager._stream_events = _stop_stream

        await manager._listen_loop()

        manager._set_sse_connected.assert_not_called()


def _event(resource_id: str, value: str, **metadata):
    event = {
        "subjectId": "g410",
        "resourceId": resource_id,
        "value": value,
        "statusCode": 0,
    }
    event.update(metadata)
    return event


def _ring_entity(coordinator: _Coordinator, *, mock_schedule: bool = True):
    entity = binary_sensor_module.AqaraBinarySensor(
        coordinator,
        "g410",
        "Doorbell",
        None,
        binary_sensors.G410_DOORBELL_RING,
        "lumi.camera.agl006",
        "Aqara G410",
    )
    if mock_schedule:
        entity._schedule_event_clear = Mock()
    return entity


def _face_entity(coordinator: _Coordinator):
    return sensor_module.AqaraSensor(
        coordinator,
        "g410",
        "Doorbell",
        sensors.G410_FACE_RECOGNITION_EVENT,
        "lumi.camera.agl006",
        "Aqara G410",
    )


def _face_event_entity(coordinator: _Coordinator):
    return event_module.AqaraG410Event(
        coordinator,
        "g410",
        "Doorbell",
        "lumi.camera.agl006",
        events.G410_FACE_RECOGNITION_EVENT,
    )


def _child_voltage_entity(coordinator: _Coordinator):
    return sensor_module.AqaraGenericChildSensor(
        coordinator,
        {
            "did": "smoke.did",
            "parent_did": "hub.did",
            "model": "lumi.sensor_smoke.acn03",
            "device_name": "Smoke detector",
            "resource_id": "8.0.2008",
            "unique_id": "smoke.did_child_8.0.2008",
            "name": "Battery voltage",
            "translation_key": "battery_voltage",
            "unit": "V",
            "value_type": "float",
            "scale": 0.001,
            "device_class": "voltage",
            "state_class": "measurement",
            "suggested_display_precision": 3,
        },
    )


class GenericChildSensorTests(unittest.TestCase):
    def test_battery_voltage_is_converted_to_volts(self):
        coordinator = _Coordinator()
        entity = _child_voltage_entity(coordinator)

        for raw in (2915, "2915"):
            with self.subTest(raw=raw):
                coordinator.data = {"8.0.2008": raw}
                self.assertEqual(entity.native_value, 2.915)

        self.assertEqual(entity._attr_native_unit_of_measurement, "V")
        self.assertEqual(entity._attr_device_class, "voltage")
        self.assertEqual(entity._attr_state_class, "measurement")
        self.assertEqual(entity._attr_suggested_display_precision, 3)

    def test_battery_voltage_handles_missing_and_invalid_values(self):
        coordinator = _Coordinator()
        entity = _child_voltage_entity(coordinator)

        self.assertIsNone(entity.native_value)

        coordinator.data = {"8.0.2008": "unknown"}
        self.assertIsNone(entity.native_value)


class G410EventTests(unittest.TestCase):
    def test_real_ring_activates_once_and_refresh_does_not_extend_it(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _ring_entity(coordinator, mock_schedule=False)
        entity.hass = object()
        clock = Mock(return_value=100.0)
        schedule = Mock(return_value=lambda: None)

        with (
            patch.object(binary_sensor_module.time, "time", clock),
            patch.object(binary_sensor_module, "async_call_later", schedule),
        ):
            manager._apply_events("batch", [_event("13.12.85", "1")])
            entity._handle_coordinator_update()
            self.assertTrue(entity.is_on)
            self.assertEqual(110.0, entity._event_active_until)

            clock.return_value = 105.0
            entity._handle_coordinator_update()
            self.assertEqual(110.0, entity._event_active_until)

            clock.return_value = 111.0
            self.assertFalse(entity.is_on)

        self.assertGreater(coordinator.data["bell_ring"], 0)
        schedule.assert_called_once()

    def test_face_after_old_ring_does_not_reactivate_ring(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _ring_entity(coordinator)
        manager._apply_events("batch", [_event("13.12.85", "1")])
        entity._handle_coordinator_update()

        manager._apply_events("batch", [_event("13.95.85", "member-7")])
        entity._handle_coordinator_update()

        entity._schedule_event_clear.assert_called_once_with()
        self.assertEqual("member-7", coordinator.data["detect_face_event"])

    def test_snapshot_with_historical_ring_is_ignored(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)

        manager._apply_events("snapshot", [_event("13.12.85", "1")])

        self.assertEqual([], coordinator.updates)
        self.assertNotIn("bell_ring", manager._g410_state["g410"])

    def test_two_ring_pushes_get_two_occurrence_ids(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _ring_entity(coordinator)

        manager._apply_events("batch", [_event("13.12.85", "1")])
        first_id = coordinator.data["bell_ring"]
        entity._handle_coordinator_update()
        manager._apply_events("batch", [_event("13.12.85", "1")])
        second_id = coordinator.data["bell_ring"]
        entity._handle_coordinator_update()

        self.assertNotEqual(first_id, second_id)
        self.assertEqual(2, entity._schedule_event_clear.call_count)

    def test_two_ring_events_in_one_batch_are_published_separately(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)

        manager._apply_events(
            "batch",
            [_event("13.12.85", "1"), _event("13.12.85", "1")],
        )

        self.assertEqual(2, len(coordinator.updates))
        self.assertNotEqual(
            coordinator.updates[0]["bell_ring"],
            coordinator.updates[1]["bell_ring"],
        )

    def test_two_identical_face_recognitions_are_both_represented(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_entity(coordinator)

        manager._apply_events("batch", [_event("13.95.85", "member-7")])
        entity._handle_coordinator_update()
        first_event_id = entity._attr_extra_state_attributes["event_id"]
        manager._apply_events("batch", [_event("13.95.85", "member-7")])
        entity._handle_coordinator_update()
        second_event_id = entity._attr_extra_state_attributes["event_id"]

        self.assertEqual("member-7", entity._attr_native_value)
        self.assertNotEqual(first_event_id, second_event_id)
        self.assertEqual(2, entity._write_count)

    def test_two_identical_face_recognitions_trigger_two_events(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)

        manager._apply_events(
            "batch",
            [_event("13.95.85", "member-7", msgId="first", time=1710000000000)],
        )
        entity._handle_coordinator_update()
        manager._apply_events(
            "batch",
            [_event("13.95.85", "member-7", msgId="second", time=1710000001000)],
        )
        entity._handle_coordinator_update()

        self.assertEqual(
            [
                ("recognized", {"member_id": "member-7", "time": 1710000000000}),
                ("recognized", {"member_id": "member-7", "time": 1710000001000}),
            ],
            entity._triggered_events,
        )

    def test_face_recognitions_without_msg_id_get_unique_events(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)

        for _ in range(2):
            manager._apply_events(
                "batch",
                [_event("13.95.85", "member-7", time=1710000000000)],
            )
            entity._handle_coordinator_update()

        self.assertEqual(2, len(entity._triggered_events))

    def test_different_members_without_msg_id_get_unique_events(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)

        for member_id in ("member-7", "member-8"):
            manager._apply_events(
                "batch",
                [_event("13.95.85", member_id, time=1710000000000)],
            )
            entity._handle_coordinator_update()

        self.assertEqual(
            ["member-7", "member-8"],
            [event_data["member_id"] for _, event_data in entity._triggered_events],
        )

    def test_replayed_msg_id_is_handled_once(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)
        payload = _event(
            "13.95.85",
            "member-7",
            msgId="same-message",
            time=1710000000000,
        )

        for _ in range(2):
            manager._apply_events("batch", [payload])
            entity._handle_coordinator_update()

        self.assertEqual(1, len(entity._triggered_events))

    def test_delayed_replayed_msg_id_is_handled_once(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)
        first = _event(
            "13.95.85",
            "member-7",
            msgId="first-message",
            time=1710000000000,
        )
        second = _event(
            "13.95.85",
            "member-8",
            msgId="second-message",
            time=1710000001000,
        )

        for payload in (first, second, first):
            manager._apply_events("batch", [payload])
            entity._handle_coordinator_update()

        self.assertEqual(
            ["member-7", "member-8"],
            [event_data["member_id"] for _, event_data in entity._triggered_events],
        )

    def test_face_event_without_time_does_not_reuse_previous_time(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)
        entity = _face_event_entity(coordinator)

        manager._apply_events(
            "batch",
            [_event("13.95.85", "member-7", msgId="first", time=1710000000000)],
        )
        entity._handle_coordinator_update()
        manager._apply_events(
            "batch",
            [_event("13.95.85", "member-7", msgId="second")],
        )
        entity._handle_coordinator_update()

        self.assertEqual(
            ("recognized", {"member_id": "member-7"}),
            entity._triggered_events[-1],
        )

    def test_known_g410_log_hashes_member_id(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)

        with self.assertLogs(push_module._LOGGER, level="DEBUG") as logs:
            manager._apply_events(
                "batch",
                [_event("13.95.85", "private-member-id", msgId="first", time=1710000000000)],
            )

        self.assertTrue(any("valueHash=" in line for line in logs.output))
        self.assertFalse(any("private-member-id" in line for line in logs.output))

    def test_event_resources_are_not_queryable(self):
        self.assertFalse(binary_sensors.G410_DOORBELL_RING["queryable"])
        self.assertFalse(sensors.G410_FACE_RECOGNITION_EVENT["queryable"])

    def test_g410_resources_are_filtered_by_model(self):
        acn017_resources = set(
            bridge_specs.g410_resource_spec_map_for_model("lumi.camera.acn017")
        )
        agl006_resources = set(
            bridge_specs.g410_resource_spec_map_for_model("lumi.camera.agl006")
        )

        common_resources = {
            "8.0.2001",
            "14.11.85",
            "4.67.85",
            "4.55.85",
            "14.1.85",
            "14.110.85",
            "13.95.85",
            "13.12.85",
            "14.1.111",
            "14.1.1000",
            "14.65.85",
            "4.8.85",
            "4.66.85",
            "4.54.85",
            "4.68.85",
        }
        agl006_only_resources = {
            "14.75.85",
        }
        acn017_only_resources = {
            "14.68.85",
            "14.125.85",
            "13.108.85",
            "8.0.2032",
            "4.154.85",
            "4.138.85",
        }

        self.assertEqual(common_resources | agl006_only_resources, agl006_resources)
        self.assertEqual(common_resources | acn017_only_resources, acn017_resources)

    def test_agl006_face_detection_switch_uses_documented_payload(self):
        specs = bridge_specs.g410_state_specs_for_model("lumi.camera.agl006")
        face_detection = next(
            spec for spec in specs if spec.get("inApp") == "face_detect_enable"
        )

        self.assertEqual("14.75.85", face_detection["api"])
        self.assertEqual({"14.75.85": 1}, face_detection["on_data"])
        self.assertEqual({"14.75.85": 0}, face_detection["off_data"])
        self.assertNotIn(
            "14.75.85",
            bridge_specs.g410_resource_spec_map_for_model("lumi.camera.acn017"),
        )

    def test_stranger_face_resource_is_subscribed_only_for_acn017(self):
        enabled_unique_ids = {"g410_detect_stranger_face_event"}
        acn017_subscriptions = bridge_specs.build_active_subscriptions(
            enabled_unique_ids=enabled_unique_ids,
            cameras=[],
            g2h_pro_cameras=[],
            g410_doorbells=[{"did": "g410", "model": "lumi.camera.acn017"}],
            g4_doorbells=[],
            hubs_m3=[],
            hubs_m100=[],
            hubs_m200=[],
            a100_pro_locks=[],
            acn002_locks=[],
            presence_devices=[],
        )
        agl006_subscriptions = bridge_specs.build_active_subscriptions(
            enabled_unique_ids=enabled_unique_ids,
            cameras=[],
            g2h_pro_cameras=[],
            g410_doorbells=[{"did": "g410", "model": "lumi.camera.agl006"}],
            g4_doorbells=[],
            hubs_m3=[],
            hubs_m100=[],
            hubs_m200=[],
            a100_pro_locks=[],
            acn002_locks=[],
            presence_devices=[],
        )
        g4_subscriptions = bridge_specs.build_active_subscriptions(
            enabled_unique_ids={"g4_detect_stranger_face_event"},
            cameras=[],
            g2h_pro_cameras=[],
            g410_doorbells=[],
            g4_doorbells=[{"did": "g4"}],
            hubs_m3=[],
            hubs_m100=[],
            hubs_m200=[],
            a100_pro_locks=[],
            acn002_locks=[],
            presence_devices=[],
        )

        self.assertIn("13.108.85", bridge_specs.G4_RESOURCE_SPEC_MAP)
        self.assertEqual(
            [{"subjectId": "g410", "resourceIds": ["13.108.85"]}],
            acn017_subscriptions,
        )
        self.assertEqual([], agl006_subscriptions)
        self.assertEqual(
            [{"subjectId": "g4", "resourceIds": ["13.108.85"]}],
            g4_subscriptions,
        )

    def test_registry_cleanup_keeps_acn017_and_removes_agl006_entity(self):
        registry = SimpleNamespace(async_remove=Mock())
        obsolete_keys = {
            "detect_stranger_face_event",
            "time_sleep_enable",
            "device_night_tip_light",
            "doorbell_push_enable",
            "doorbell_record_enable",
            "image_flip",
            "restart_device",
            "restart_coordinator",
        }
        entries = [
            SimpleNamespace(
                entity_id="sensor.acn017_stranger_face",
                unique_id="acn017_detect_stranger_face_event",
            ),
            SimpleNamespace(
                entity_id="sensor.g4_stranger_face",
                unique_id="g4_detect_stranger_face_event",
            ),
            *[
                SimpleNamespace(
                    entity_id=f"test.agl006_{key}",
                    unique_id=f"agl006_{key}",
                )
                for key in obsolete_keys
            ],
        ]

        with (
            patch.object(entity_migration.er, "async_get", return_value=registry),
            patch.object(
                entity_migration.er,
                "async_entries_for_config_entry",
                return_value=entries,
            ),
        ):
            entity_migration.remove_obsolete_g410_entities(
                object(),
                "entry-id",
                [
                    {"did": "acn017", "model": "lumi.camera.acn017"},
                    {"did": "agl006", "model": "lumi.camera.agl006"},
                ],
            )

        self.assertEqual(
            {f"test.agl006_{key}" for key in obsolete_keys},
            {call.args[0] for call in registry.async_remove.call_args_list},
        )

    def test_stranger_face_push_is_accepted_for_acn017(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator, "lumi.camera.acn017")

        manager._apply_events(
            "batch",
            [_event("13.108.85", "0", msgId="stranger", time=1710000000000)],
        )

        self.assertEqual("0", coordinator.data["detect_stranger_face_event"])
        self.assertEqual(1, len(coordinator.updates))

    def test_unknown_g410_resource_is_logged_without_state_update(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)

        with self.assertLogs(push_module._LOGGER, level="DEBUG") as logs:
            manager._apply_events("batch", [_event("13.108.85", "Lingerer")])

        self.assertEqual([], coordinator.updates)
        self.assertTrue(
            any(
                "subjectId=g410 resourceId=13.108.85 valueHash=" in line
                for line in logs.output
            )
        )
        self.assertFalse(any("Lingerer" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
