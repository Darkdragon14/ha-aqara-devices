from __future__ import annotations
from datetime import timedelta
from typing import Dict, Any
import logging


from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.number import NumberEntity

from .const import DOMAIN, G3_MODEL, G3_DEVICE_LABEL, M3_DEVICE_LABEL
from .numbers import ALL_NUMBERS_DEF, M3_NUMBERS_DEF
from .api import AqaraApi
from .device_info import build_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    cameras: list[dict] = data["cameras"]
    hubs_m3: list[dict] = data.get("hubs_m3", [])

    entities = []

    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam.get("model") or G3_MODEL

        async def _async_update_video_data(did_local=did):
            try:
                return await api.get_device_states(did_local, ALL_NUMBERS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-camera-active-{did}",
            update_method=_async_update_video_data,
            update_interval=timedelta(seconds=1),
        )

        for number_def in ALL_NUMBERS_DEF:
            number = AqaraNumber(coordinator, api, did, name, number_def, model, G3_DEVICE_LABEL)
            entities.append(number)

    for hub in hubs_m3:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]

        async def _async_update_m3_data(did_local=did):
            try:
                return await api.get_device_states(did_local, M3_NUMBERS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-hub-m3-number-{did}",
            update_method=_async_update_m3_data,
            update_interval=timedelta(seconds=1),
        )

        for number_def in M3_NUMBERS_DEF:
            number = AqaraNumber(coordinator, api, did, name, number_def, model, M3_DEVICE_LABEL)
            entities.append(number)
        
    async_add_entities(entities, True)

class AqaraNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api: AqaraApi,
        did: str,
        device_name: str,
        spec: Dict[str, Any],
        model: str,
        device_label: str,
    ) -> None:
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._api = api
        self._spec = spec
        self._model = model
        self._device_label = device_label

        self._attr_unique_id = f"{did}_{spec['inApp']}"
        self._native_value: float | None = None
        self._attr_name = "System Volume"
        self._attr_native_min_value = float(spec['min'])
        self._attr_native_max_value = float(spec['max'])
        self._attr_native_step = float(spec["step"])
        self._attr_name = spec["name"]
        self._attr_icon = spec["icon"]

    
    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @property
    def native_value(self):
        return self._native_value

    async def async_set_native_value(self, value: float):
        v = max(self._attr_native_min_value, min(self._attr_native_max_value, float(value)))

        self._native_value = v
        self.async_write_ha_state()
        payload = {
            "data": {
                self._spec["api"]: int(v)
            },
            "subjectId": self._did,
        }
        await self._api.res_write(payload)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        if raw is None:
            return
        self._native_value = float(raw)
        self.async_write_ha_state()
