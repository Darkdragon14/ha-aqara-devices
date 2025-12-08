from __future__ import annotations
from datetime import timedelta
from typing import Dict, Any
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .binary_sensors import ALL_BINARY_SENSORS_DEF
from .api import AqaraApi

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    cameras: list[dict] = data["cameras"]

    entities = []

    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]

        async def _async_update_video_data(did_local=did):
            try:
                return await api.get_device_states(did_local)
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
            switch = AqaraG3BinarySensor(
                coordinator,
                did,
                name,
                api,
                binary_sensor_def,
            )
            entities.append(switch)

    async_add_entities(entities)

class AqaraG3BinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        api: AqaraApi,
        spec: Dict[str, Any],
    ):
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._api = api
        self._spec = spec

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
        return {
            "identifiers": {(DOMAIN, self._did)},
            "manufacturer": "Aqara",
            "model": "Camera Hub G3",
            "name": f"Aqara G3 ({self._device_name})",
            "model_id": self._did,
            "model": "lumi.camera.gwpgl1",
        }

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
