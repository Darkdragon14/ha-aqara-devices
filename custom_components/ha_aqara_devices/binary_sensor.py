from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any, Dict

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AqaraApi
from .binary_sensors import ALL_BINARY_SENSORS_DEF, M3_BINARY_SENSORS_DEF
from .const import DOMAIN, FP2_DEVICE_LABEL, FP2_MODEL, G3_DEVICE_LABEL, G3_MODEL, M3_DEVICE_LABEL
from .device_info import build_device_info
from .fp2 import FP2_BINARY_SENSORS_DEF

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    cameras: list[dict] = data["cameras"]
    hubs_m3: list[dict] = data.get("hubs_m3", [])
    fp2_devices: list[dict] = data.get("fp2_devices", [])

    entities = []

    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam.get("model") or G3_MODEL

        async def _async_update_video_data(did_local=did):
            try:
                return await api.get_device_states(did_local, ALL_BINARY_SENSORS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-camera-binary_sensor-{did}",
            update_method=_async_update_video_data,
            update_interval=timedelta(seconds=1),
        )

        for binary_sensor_def in ALL_BINARY_SENSORS_DEF:
            entities.append(
                AqaraBinarySensor(
                    coordinator,
                    did,
                    name,
                    api,
                    binary_sensor_def,
                    model,
                    G3_DEVICE_LABEL,
                )
            )

    for hub in hubs_m3:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]

        async def _async_update_m3_data(did_local=did):
            try:
                return await api.get_device_states(did_local, M3_BINARY_SENSORS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-hub-m3-binary_sensor-{did}",
            update_method=_async_update_m3_data,
            update_interval=timedelta(seconds=1),
        )

        for binary_sensor_def in M3_BINARY_SENSORS_DEF:
            entities.append(
                AqaraBinarySensor(
                    coordinator,
                    did,
                    name,
                    api,
                    binary_sensor_def,
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
            name=f"{DOMAIN}-fp2-binary_sensor-{did}",
            update_method=_async_update_fp2_data,
            update_interval=timedelta(seconds=2),
        )
        await coordinator.async_config_entry_first_refresh()

        for spec in FP2_BINARY_SENSORS_DEF:
            entities.append(
                AqaraFP2BinarySensor(
                    coordinator,
                    did,
                    name,
                    spec,
                )
            )

    async_add_entities(entities)


class AqaraBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        api: AqaraApi,
        spec: Dict[str, Any],
        model: str,
        device_label: str,
    ):
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._api = api
        self._spec = spec
        self._model = model
        self._device_label = device_label

        self._attr_name = spec["name"]
        self._attr_icon = spec["icon"]
        self._attr_unique_id = f"{did}_{spec['inApp']}"
        self._attr_translation_key = spec.get("translation_key")
        self._value_type = spec.get("value_type")
        self._hold_seconds = spec.get("hold_seconds", 5)

        device_class = spec.get("device_class")
        if isinstance(device_class, BinarySensorDeviceClass):
            self._attr_device_class = device_class
        elif isinstance(device_class, str):
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                self._attr_device_class = BinarySensorDeviceClass.POWER
        else:
            self._attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @staticmethod
    def _truthy(val: Any) -> bool:
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ("1", "true", "on", "yes"):
            return True
        if s.isdigit():
            return int(s) != 0
        try:
            return bool(int(val))
        except Exception:
            return False

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        if self._value_type == "timestamp":
            if not raw:
                return False
            try:
                ts = float(raw)
            except (TypeError, ValueError):
                return False
            if ts > 1_000_000_000_000:  # milliseconds
                ts /= 1000.0
            now = time.time()
            if ts <= 0 or ts > now + 5:
                return False
            return (now - ts) <= max(self._hold_seconds, 1)
        return self._truthy(raw)


class AqaraFP2BinarySensor(CoordinatorEntity, BinarySensorEntity):
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
        self._fallback_key = spec.get("fallback_key")
        self._on_values = {str(v) for v in spec.get("on_values", set())}
        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")
        self._attr_unique_id = f"{did}_fp2_{self._key}"
        self._attr_entity_registry_enabled_default = spec.get("enabled_default", True)
        device_class = spec.get("device_class")
        if isinstance(device_class, BinarySensorDeviceClass):
            self._attr_device_class = device_class
        elif isinstance(device_class, str):
            try:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
            except ValueError:
                self._attr_device_class = None
        else:
            self._attr_device_class = None

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, FP2_MODEL, FP2_DEVICE_LABEL)

    def _coordinator_value(self):
        data = self.coordinator.data or {}
        if self._key in data:
            return data.get(self._key)
        if self._fallback_key and self._fallback_key in data:
            return data.get(self._fallback_key)
        return None

    @property
    def is_on(self) -> bool:
        raw = self._coordinator_value()
        if raw is None:
            return False
        if self._on_values:
            return str(raw) in self._on_values
        return str(raw).strip() not in ("0", "false", "off")
