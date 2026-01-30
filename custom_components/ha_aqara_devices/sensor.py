from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, FP2_MODEL
from .api import AqaraApi
from .fp2 import FP2_SENSOR_SPECS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    fp2_devices: list[dict] = data.get("fp2_devices", [])

    entities: list[AqaraFP2Sensor] = []

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

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._did)},
            "manufacturer": "Aqara",
            "model": "Presence Sensor FP2",
            "name": f"Aqara FP2 ({self._device_name})",
            "model_id": self._did,
            "model": FP2_MODEL,
        }

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
