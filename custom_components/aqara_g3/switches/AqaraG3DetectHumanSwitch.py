from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)

from ..const import DOMAIN, DETECT_HUMAN_ACTIVE

class AqaraG3DetectHumanSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Detect Human"
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: DataUpdateCoordinator, did: str, api):
        super().__init__(coordinator)
        self._did = did
        self._api = api
        self._attr_unique_id = f"{did}_{DETECT_HUMAN_ACTIVE['inApp']}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._did)},
            "manufacturer": "Aqara",
            "model": "Camera Hub G3",
            "name": f"Aqara G3 ({self._did})",
        }

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        val = data.get(DETECT_HUMAN_ACTIVE["inApp"])
        try:
            return bool(int(val))
        except Exception:
            return str(val).lower() in ("1", "on", "true")

    async def async_turn_on(self, **kwargs):
        payload = {"data": {DETECT_HUMAN_ACTIVE["api"]:"1","human_detect_enable":"1","pets_track_enable":"0","ptz_cruise_enable":"0","gesture_detect_enable":"0"}, "subjectId": self._did}
        data = await self._api.res_write(payload)
        if str(data.get("code")) != "0":
            raise Exception(f"Aqara API error: {data}")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        payload = {"data": {DETECT_HUMAN_ACTIVE["api"]: 0}, "subjectId": self._did}
        data = await self._api.res_write(payload)
        if str(data.get("code")) != "0":
            raise Exception(f"Aqara API error: {data}")
        await self.coordinator.async_request_refresh()