from __future__ import annotations

import importlib
from pathlib import Path
import sys
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
    stub("homeassistant.config_entries", ConfigEntry=object)
    stub(
        "homeassistant.const",
        PERCENTAGE="%",
        UnitOfTemperature=_EnumLike,
    )
    stub("homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    stub("homeassistant.helpers")
    stub("homeassistant.helpers.event", async_call_later=lambda *args: lambda: None)
    stub(
        "homeassistant.helpers.update_coordinator",
        CoordinatorEntity=_CoordinatorEntity,
        DataUpdateCoordinator=object,
    )

    class AqaraAuthError(RuntimeError):
        pass

    stub(f"{PACKAGE}.api", AqaraApi=object, AqaraAuthError=AqaraAuthError)
    stub(f"{PACKAGE}.device_info", build_device_info=lambda *args: {})
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
            importlib.import_module(f"{PACKAGE}.binary_sensors"),
            importlib.import_module(f"{PACKAGE}.sensors"),
        )
    return modules


(
    bridge_specs,
    binary_sensor_module,
    push_module,
    sensor_module,
    binary_sensors,
    sensors,
) = _import_test_modules()


class _Coordinator:
    name = "g410-state"
    update_interval = None

    def __init__(self):
        self.data = {}
        self.updates = []

    def async_set_updated_data(self, data):
        self.data = data
        self.updates.append(data)


def _manager(coordinator: _Coordinator):
    manager = push_module.AqaraBridgePushManager.__new__(push_module.AqaraBridgePushManager)
    manager._event_id = 0
    manager._cameras = {}
    manager._g2h_pro_cameras = {}
    manager._g410_doorbells = {"g410": {"did": "g410"}}
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


def _event(resource_id: str, value: str):
    return {
        "subjectId": "g410",
        "resourceId": resource_id,
        "value": value,
        "statusCode": 0,
    }


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

    def test_event_resources_are_not_queryable(self):
        self.assertFalse(binary_sensors.G410_DOORBELL_RING["queryable"])
        self.assertFalse(sensors.G410_FACE_RECOGNITION_EVENT["queryable"])
        self.assertFalse(sensors.G410_STRANGER_FACE_EVENT["queryable"])

    def test_unknown_g410_resource_is_logged_without_state_update(self):
        coordinator = _Coordinator()
        manager = _manager(coordinator)

        with self.assertLogs(push_module._LOGGER, level="DEBUG") as logs:
            manager._apply_events("batch", [_event("13.999.85", "Lingerer")])

        self.assertEqual([], coordinator.updates)
        self.assertIn("subjectId=g410 resourceId=13.999.85 value='Lingerer'", logs.output[0])


if __name__ == "__main__":
    unittest.main()
