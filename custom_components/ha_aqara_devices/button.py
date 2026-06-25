from __future__ import annotations
import asyncio
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .api import AqaraApi
from .const import DOMAIN, G2H_PRO_DEVICE_LABEL, G410_DEVICE_LABEL, G4_DEVICE_LABEL, G3_MODEL, G3_DEVICE_LABEL
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
    "ring_alarm_bell": "mdi:bell-alert",
    "restart_device": "mdi:restart",
    "restart_coordinator": "mdi:zigbee",
}

RING_ALARM_BELL = "14.1.111"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    cameras: list[dict] = data["cameras"]
    g2h_pro_cameras: list[dict] = data.get("g2h_pro_cameras", [])
    g410_doorbells: list[dict] = data.get("g410_doorbells", [])
    g4_doorbells: list[dict] = data.get("g4_doorbells", [])

    entities: list[ButtonEntity] = []
    for cam in cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam.get("model") or G3_MODEL
        entities.append(AqaraG3RingAlarmBell(api, did, name, model))
        for direction in ("up", "down", "left", "right"):
            entities.append(AqaraG3PTZButton(api, did, name, model, direction))

    for cam in g2h_pro_cameras:
        did = cam["did"]
        name = cam["deviceName"]
        model = cam["model"]
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G2H_PRO_DEVICE_LABEL,
                "Restart Device",
                "restart_device",
                "8.0.2108",
                0,
            )
        )
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G2H_PRO_DEVICE_LABEL,
                "Restart Coordinator",
                "restart_coordinator",
                "8.0.2108",
                1,
            )
        )

    for doorbell in g410_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G410_DEVICE_LABEL,
                "Restart Device",
                "restart_device",
                "8.0.2108",
                0,
            )
        )
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G410_DEVICE_LABEL,
                "Restart Coordinator",
                "restart_coordinator",
                "8.0.2108",
                1,
            )
        )

    for doorbell in g4_doorbells:
        did = doorbell["did"]
        name = doorbell["deviceName"]
        model = doorbell["model"]
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G4_DEVICE_LABEL,
                "Restart Device",
                "restart_device",
                "8.0.2108",
                0,
            )
        )
        entities.append(
            AqaraResourceButton(
                api,
                did,
                name,
                model,
                G4_DEVICE_LABEL,
                "Restart Coordinator",
                "restart_coordinator",
                "8.0.2108",
                1,
            )
        )

    async_add_entities(entities)


class AqaraG3PTZButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, api: AqaraApi, did: str, device_name: str, model: str, direction: str) -> None:
        self._api = api
        self._did = did
        self._direction = direction
        self._attr_translation_key = f"ptz_{direction}"
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
        self._attr_translation_key = "ring_alarm_bell"
        self._attr_icon = ICONS["ring_alarm_bell"]
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


class AqaraResourceButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        api: AqaraApi,
        did: str,
        device_name: str,
        model: str,
        device_label: str,
        name: str,
        key: str,
        resource_id: str,
        value: int,
    ) -> None:
        self._api = api
        self._did = did
        self._device_name = device_name
        self._model = model
        self._device_label = device_label
        self._resource_id = resource_id
        self._value = value
        self._attr_translation_key = key
        self._attr_icon = ICONS[key]
        self._attr_unique_id = f"{did}_{key}"

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    async def async_press(self) -> None:
        payload = {
            "data": {
                self._resource_id: self._value,
            },
            "subjectId": self._did,
        }
        resp = await self._api.res_write(payload)
        if str(resp.get("code")) != "0":
            raise Exception(f"Aqara API error: {resp}")
