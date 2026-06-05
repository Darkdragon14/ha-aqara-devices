from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    A100_PRO_DEVICE_LABEL,
    DOMAIN,
    FP2_DEVICE_LABEL,
    FP2_MODEL,
    FP300_DEVICE_LABEL,
    FP300_MODEL,
    G410_DEVICE_LABEL,
    G4_DEVICE_LABEL,
    M100_DEVICE_LABEL,
    M3_DEVICE_LABEL,
)
from .device_info import build_device_info
from .fp300 import FP300_SENSOR_SPECS
from .fp2 import FP2_SENSOR_SPECS
from .sensors import (
    A100_PRO_SENSORS_DEF,
    G410_SENSORS_DEF,
    G4_SENSORS_DEF,
    M100_SENSORS_DEF,
    M3_SENSORS_DEF,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    g410_doorbells: list[dict] = data.get("g410_doorbells", [])
    g4_doorbells: list[dict] = data.get("g4_doorbells", [])
    hubs_m3: list[dict] = data.get("hubs_m3", [])
    hubs_m100: list[dict] = data.get("hubs_m100", [])
    a100_pro_locks: list[dict] = data.get("a100_pro_locks", [])
    presence_devices: list[dict] = data.get("presence_devices", [])
    g410_coordinators: dict[str, DataUpdateCoordinator] = data.get("g410_coordinators", {})
    g4_coordinators: dict[str, DataUpdateCoordinator] = data.get("g4_coordinators", {})
    m3_coordinators: dict[str, DataUpdateCoordinator] = data.get("m3_coordinators", {})
    m100_coordinators: dict[str, DataUpdateCoordinator] = data.get("m100_coordinators", {})
    a100_pro_coordinators: dict[str, DataUpdateCoordinator] = data.get("a100_pro_coordinators", {})
    presence_coordinators: dict[str, dict[str, DataUpdateCoordinator]] = data.get("presence_coordinators", {})

    entities: list[SensorEntity] = []

    for doorbell in g410_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        coordinator = g410_coordinators.get(did)
        if coordinator is None:
            continue

        for sensor_def in G410_SENSORS_DEF:
            entities.append(
                AqaraSensor(
                    coordinator,
                    did,
                    name,
                    sensor_def,
                    model,
                    G410_DEVICE_LABEL,
                )
            )

    for doorbell in g4_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        coordinator = g4_coordinators.get(did)
        if coordinator is None:
            continue

        for sensor_def in G4_SENSORS_DEF:
            entities.append(
                AqaraSensor(
                    coordinator,
                    did,
                    name,
                    sensor_def,
                    model,
                    G4_DEVICE_LABEL,
                )
            )

    for hub in hubs_m3:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]
        coordinator = m3_coordinators.get(did)
        if coordinator is None:
            continue

        for sensor_def in M3_SENSORS_DEF:
            entities.append(
                AqaraSensor(
                    coordinator,
                    did,
                    name,
                    sensor_def,
                    model,
                    M3_DEVICE_LABEL,
                )
            )

    for hub in hubs_m100:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]
        coordinator = m100_coordinators.get(did)
        if coordinator is None:
            continue

        for sensor_def in M100_SENSORS_DEF:
            entities.append(
                AqaraSensor(
                    coordinator,
                    did,
                    name,
                    sensor_def,
                    model,
                    M100_DEVICE_LABEL,
                )
            )

    for lock in a100_pro_locks:
        did = lock["did"]
        name = lock["deviceName"]
        model = lock["model"]
        coordinator = a100_pro_coordinators.get(did)
        if coordinator is None:
            continue

        for sensor_def in A100_PRO_SENSORS_DEF:
            entities.append(
                AqaraSensor(
                    coordinator,
                    did,
                    name,
                    sensor_def,
                    model,
                    A100_PRO_DEVICE_LABEL,
                )
            )

    for presence in presence_devices:
        did = presence["did"]
        name = presence["deviceName"]
        model = presence.get("model") or ""
        if model == FP2_MODEL:
            specs = FP2_SENSOR_SPECS
            device_label = FP2_DEVICE_LABEL
        elif model == FP300_MODEL:
            specs = FP300_SENSOR_SPECS
            device_label = FP300_DEVICE_LABEL
        else:
            continue

        device_coordinators = presence_coordinators.get(did)
        if not device_coordinators:
            continue

        for spec in specs:
            coordinator = device_coordinators.get(spec.get("poll_group", "medium"))
            if coordinator is None:
                continue
            entities.append(
                AqaraFP2Sensor(
                    coordinator,
                    did,
                    name,
                    spec,
                    model,
                    device_label,
                )
            )

    async_add_entities(entities)


class AqaraSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        spec: Dict[str, Any],
        model: str,
        device_label: str,
    ) -> None:
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._spec = spec
        self._model = model
        self._device_label = device_label

        self._attr_unique_id = f"{did}_{spec['inApp']}"
        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")
        self._attr_native_unit_of_measurement = spec.get("unit")

        device_class = spec.get("device_class")
        if isinstance(device_class, SensorDeviceClass):
            self._attr_device_class = device_class
        elif isinstance(device_class, str):
            try:
                self._attr_device_class = SensorDeviceClass(device_class)
            except ValueError:
                self._attr_device_class = None

        state_class = spec.get("state_class")
        if isinstance(state_class, SensorStateClass):
            self._attr_state_class = state_class
        elif isinstance(state_class, str):
            try:
                self._attr_state_class = SensorStateClass(state_class)
            except ValueError:
                self._attr_state_class = None

        self._attr_native_value = None
        self._value_map = spec.get("value_map") or {}

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        if raw is None:
            return
        self._attr_native_value = self._value_map.get(str(raw), raw)
        self.async_write_ha_state()


class AqaraFP2Sensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        spec: Dict[str, Any],
        model: str,
        device_label: str,
    ):
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._spec = spec
        self._model = model
        self._device_label = device_label
        self._key = spec["key"]

        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")
        self._attr_unique_id = f"{did}_fp2_sensor_{self._key}"
        self._value_type = spec.get("value_type")
        self._value_map = spec.get("value_map") or {}
        self._scale = spec.get("scale")
        self._attr_native_unit_of_measurement = spec.get("unit")
        self._attr_device_class = spec.get("device_class")
        self._attr_state_class = spec.get("state_class")
        self._attr_entity_registry_enabled_default = spec.get("enabled_default", True)

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        raw = data.get(self._key)
        if raw is None:
            return None
        if self._value_map:
            return self._value_map.get(str(raw), raw)

        def _apply_scale(value: int | float):
            if self._scale is None:
                return value
            try:
                return float(value) * float(self._scale)
            except (TypeError, ValueError):
                return value

        if self._value_type == "int":
            try:
                parsed = int(raw)
            except (TypeError, ValueError):
                return None
            return _apply_scale(parsed)
        if self._value_type == "float":
            try:
                parsed = float(raw)
            except (TypeError, ValueError):
                return None
            return _apply_scale(parsed)

        if self._scale is not None:
            try:
                return float(raw) * float(self._scale)
            except (TypeError, ValueError):
                return raw

        return raw
