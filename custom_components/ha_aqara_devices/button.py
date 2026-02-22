from __future__ import annotations
from typing import Final
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .api import AqaraApi
from .const import DOMAIN, G3_MODEL, G3_DEVICE_LABEL
from .device_info import build_device_info

PTZ_ACTIONS: dict[str, str] = {
    "up": "up_always",
    "down": "down_always",
    "left": "left_always",
    "right": "right_always",
}

ICONS: dict[str, str] = {
    "up": "mdi:arrow-up-bold",
    "down": "mdi:arrow-down-bold",
    "left": "mdi:arrow-left-bold",
    "right": "mdi:arrow-right-bold",
    "alarm_status": "mdi:bell-alert",
}

RING_ALARM_BELL =  "alarm_status"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    cameras: list[dict] = data["cameras"]

    entities: list[ButtonEntity] = []
    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam.get("model") or G3_MODEL
        entities.append(AqaraG3RingAlarmBell(api, did, name, model))
        for direction in ("up", "down", "left", "right"):
            entities.append(AqaraG3PTZButton(api, did, name, model, direction))

    async_add_entities(entities)


class AqaraG3PTZButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, api: AqaraApi, did: str, device_name: str, model: str, direction: str) -> None:
        self._api = api
        self._did = did
        self._direction = direction
        self._attr_name = direction.capitalize()
        self._attr_icon = ICONS[direction]
        self._attr_unique_id = f"{did}_ptz_{direction}"
        self._device_name = device_name
        self._model = model
        self._device_label = G3_DEVICE_LABEL

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    async def async_press(self) -> None:
        action = PTZ_ACTIONS[self._direction]
        await self._api.camera_operate(self._did, action)
        await self._api.camera_operate(self._did, "stop")

class AqaraG3RingAlarmBell(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, api: AqaraApi, did: str, device_name: str, model: str) -> None:
        self._api = api
        self._did = did
        self._attr_name = "Ring Alarm Bell"
        self._attr_icon = ICONS[RING_ALARM_BELL]
        self._attr_unique_id = f"{did}_ring_alarm_bell"
        self._device_name = device_name
        self._model = model
        self._device_label = G3_DEVICE_LABEL

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    async def async_press(self) -> None:
        payload = {
            "data": {
                RING_ALARM_BELL: 1
            },
            "subjectId": self._did,
        }
        await self._api.res_write(payload)
        await asyncio.sleep(10)
        payload = {
            "data": {
                RING_ALARM_BELL: 0
            },
            "subjectId": self._did,
        }
        await self._api.res_write(payload)
