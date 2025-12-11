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

from .const import DOMAIN
from .numbers import ALL_NUMBERS_DEF
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
            name=f"{DOMAIN}-camera-active-{did}",
            update_method=_async_update_video_data,
            update_interval=timedelta(seconds=1),
        )

        for number_def in ALL_NUMBERS_DEF:
            number = AqaraG3Number(coordinator, api, did, name, number_def)
            entities.append(number)
        
    async_add_entities(entities, True)

class AqaraG3Number(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, api: AqaraApi, did: str, device_name: str, spec: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._api = api
        self._spec = spec

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
        return {
            "identifiers": {(DOMAIN, self._did)},
            "manufacturer": "Aqara",
            "model": "Camera Hub G3",
            "name": f"Aqara G3 ({self._device_name})",
            "model_id": self._did,
            "model": "lumi.camera.gwpgl1",
        }

    @property
    def native_value(self):
        return self._native_value

    async def async_set_native_value(self, value: float):
        v = max(self._attr_native_min_value, min(self._attr_native_max_value, float(value)))

        self._native_value = v
        self.async_write_ha_state()
        payload = {
            "data": {
                self._spec["api"]: int(value)
            },
            "subjectId": self._did,
        }
        await self._api.res_write(payload)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        self._native_value = float(raw)
        self.async_write_ha_state()