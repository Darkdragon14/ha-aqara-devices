from __future__ import annotations
from copy import deepcopy
from typing import Dict, Any
import logging

from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, G2H_PRO_DEVICE_LABEL, G410_DEVICE_LABEL, G4_DEVICE_LABEL, G3_MODEL, G3_DEVICE_LABEL, M100_DEVICE_LABEL
from .switches import ALL_SWITCHES_DEF, G2H_PRO_SWITCHES_DEF, G410_SWITCHES_DEF, G4_SWITCHES_DEF, M100_SWITCHES_DEF
from .api import AqaraApi
from .device_info import build_device_info

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    cameras: list[dict] = data["cameras"]
    g2h_pro_cameras: list[dict] = data.get("g2h_pro_cameras", [])
    g410_doorbells: list[dict] = data.get("g410_doorbells", [])
    g4_doorbells: list[dict] = data.get("g4_doorbells", [])
    hubs_m100: list[dict] = data.get("hubs_m100", [])
    camera_coordinators: dict[str, DataUpdateCoordinator] = data.get("camera_coordinators", {})
    g2h_pro_coordinators: dict[str, DataUpdateCoordinator] = data.get("g2h_pro_coordinators", {})
    g410_coordinators: dict[str, DataUpdateCoordinator] = data.get("g410_coordinators", {})
    g4_coordinators: dict[str, DataUpdateCoordinator] = data.get("g4_coordinators", {})
    m100_coordinators: dict[str, DataUpdateCoordinator] = data.get("m100_coordinators", {})

    entities = []

    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam.get("model") or G3_MODEL
        coordinator = camera_coordinators.get(did)
        if coordinator is None:
            continue


        for switch_def in ALL_SWITCHES_DEF:
            switch = AqaraResourceSwitch(
                coordinator,
                did,
                name,
                model,
                api,
                switch_def,
                G3_DEVICE_LABEL,
            )
            entities.append(switch)

    for cam in g2h_pro_cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam["model"]
        coordinator = g2h_pro_coordinators.get(did)
        if coordinator is None:
            continue

        for switch_def in G2H_PRO_SWITCHES_DEF:
            switch = AqaraResourceSwitch(
                coordinator,
                did,
                name,
                model,
                api,
                switch_def,
                G2H_PRO_DEVICE_LABEL,
            )
            entities.append(switch)

    for doorbell in g410_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        coordinator = g410_coordinators.get(did)
        if coordinator is None:
            continue

        for switch_def in G410_SWITCHES_DEF:
            switch = AqaraResourceSwitch(
                coordinator,
                did,
                name,
                model,
                api,
                switch_def,
                G410_DEVICE_LABEL,
            )
            entities.append(switch)

    for doorbell in g4_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        coordinator = g4_coordinators.get(did)
        if coordinator is None:
            continue

        for switch_def in G4_SWITCHES_DEF:
            switch = AqaraResourceSwitch(
                coordinator,
                did,
                name,
                model,
                api,
                switch_def,
                G4_DEVICE_LABEL,
            )
            entities.append(switch)

    for hub in hubs_m100:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]
        coordinator = m100_coordinators.get(did)
        if coordinator is None:
            continue

        for switch_def in M100_SWITCHES_DEF:
            switch = AqaraResourceSwitch(
                coordinator,
                did,
                name,
                model,
                api,
                switch_def,
                M100_DEVICE_LABEL,
            )
            entities.append(switch)

    async_add_entities(entities)

class AqaraResourceSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        model: str,
        api: AqaraApi,
        spec: Dict[str, Any],
        device_label: str,
    ):
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._api = api
        self._spec = spec
        self._model = model
        self._device_label = device_label

        translation_key = spec.get("translation_key")
        if translation_key:
            self._attr_translation_key = translation_key
        else:
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
