from __future__ import annotations
from datetime import timedelta
from copy import deepcopy
from typing import Dict, Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, G3_MODEL, G3_DEVICE_LABEL
from .switches import ALL_SWITCHES_DEF
from .api import AqaraApi
from .device_info import build_device_info

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
                return await api.get_device_states(did_local, ALL_SWITCHES_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-camera-active-{did}",
            update_method=_async_update_video_data,
            update_interval=timedelta(seconds=1),
        )


        for switch_def in ALL_SWITCHES_DEF:
            switch = AqaraG3Switch(
                coordinator,
                did,
                name,
                api,
                switch_def,
            )
            entities.append(switch)

    async_add_entities(entities)

class AqaraG3Switch(CoordinatorEntity, SwitchEntity):
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
        self._model = G3_MODEL
        self._device_label = G3_DEVICE_LABEL

        self._attr_name = spec["name"]
        self._attr_icon = spec["icon"]
        self._attr_unique_id = f"{did}_{spec['inApp']}"

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
        return self._truthy(raw)

    async def async_turn_on(self, **kwargs):
        payload = {
            "data": deepcopy(self._spec["on_data"]),
            "subjectId": self._did,
        }

        resp = await self._api.res_write(payload)
        if str(resp.get("code")) != "0":
            raise Exception(f"Aqara API error: {resp}")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        payload = {
            "data": deepcopy(self._spec["off_data"]),
            "subjectId": self._did,
        }
        
        resp = await self._api.res_write(payload)
        if str(resp.get("code")) != "0":
            raise Exception(f"Aqara API error: {resp}")
        await self.coordinator.async_request_refresh()
