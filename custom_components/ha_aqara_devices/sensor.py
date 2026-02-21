from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AqaraApi
from .const import DOMAIN, FP2_DEVICE_LABEL, FP2_MODEL, M3_DEVICE_LABEL
from .device_info import build_device_info
from .fp2 import FP2_SENSOR_SPECS
from .sensors import M3_SENSORS_DEF

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    hubs_m3: list[dict] = data.get("hubs_m3", [])
    fp2_devices: list[dict] = data.get("fp2_devices", [])

    entities: list[SensorEntity] = []

    for hub in hubs_m3:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]

        async def _async_update_m3_data(did_local=did):
            try:
                return await api.get_device_states(did_local, M3_SENSORS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-hub-m3-sensor-{did}",
            update_method=_async_update_m3_data,
            update_interval=timedelta(seconds=1),
        )

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

    for fp2 in fp2_devices:
        did = fp2["did"]
        name = fp2["deviceName"]

        async def _async_update_fp2_data(did_local=did):
            try:
                return await api.get_fp2_full_state(did_local)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-fp2-sensor-{did}",
            update_method=_async_update_fp2_data,
            update_interval=timedelta(seconds=2),
        )
        await coordinator.async_config_entry_first_refresh()

        for spec in FP2_SENSOR_SPECS:
            entities.append(
                AqaraFP2Sensor(
                    coordinator,
                    did,
                    name,
                    spec,
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

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        if raw is None:
            return
        self._attr_native_value = raw
        self.async_write_ha_state()


class AqaraFP2Sensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        spec: Dict[str, Any],
    ):
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._spec = spec
        self._key = spec["key"]

        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")
        self._attr_unique_id = f"{did}_fp2_sensor_{self._key}"
        self._value_type = spec.get("value_type")
        self._value_map = spec.get("value_map") or {}
        self._attr_native_unit_of_measurement = spec.get("unit")
        self._attr_device_class = spec.get("device_class")
        self._attr_state_class = spec.get("state_class")
        self._attr_entity_registry_enabled_default = spec.get("enabled_default", True)

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, FP2_MODEL, FP2_DEVICE_LABEL)

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        raw = data.get(self._key)
        if raw is None:
            return None
        if self._value_map:
            return self._value_map.get(str(raw), raw)
        if self._value_type == "int":
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None
        if self._value_type == "float":
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
        return raw
