from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, CAMERA_ACTIVE

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    did = data["did"]

    async def _async_update_data():
        try:
            # Fetch latest set_video value (0/1)
            return await api.get_camera_active(did)
        except Exception as e:
            # Never raise ConfigEntryNotReady from a platform; let the coordinator handle retries
            raise UpdateFailed(str(e)) from e

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aqara_g3__camera_active",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=1),
    )

    # Do NOT call async_config_entry_first_refresh() here to avoid bubbling setup errors
    async_add_entities([AqaraG3VideoSwitch(coordinator, did, api)], True)

    # Kick off the first refresh in the background; errors will be logged by the coordinator
    hass.async_create_task(coordinator.async_request_refresh())

class AqaraG3VideoSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Video"
    _attr_icon = "mdi:video"

    def __init__(self, coordinator: DataUpdateCoordinator, did: str, api):
        super().__init__(coordinator)
        self._did = did
        self._api = api
        self._attr_unique_id = f"{did}_camera_active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, did)},
            "manufacturer": "Aqara",
            "model": "Camera Hub G3",
            "name": f"Aqara G3 ({did})",
        }

    @property
    def is_on(self) -> bool:
        val = self.coordinator.data
        try:
            return bool(int(val))
        except Exception:
            return str(val).lower() in ("1", "on", "true")

    async def async_turn_on(self, **kwargs):
        payload = {"data": {CAMERA_ACTIVE["write"]: 1}, "subjectId": self._did}
        data = await self._api.res_write(payload)
        if str(data.get("code")) != "0":
            raise Exception(f"Aqara API error: {data}")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        payload = {"data": {CAMERA_ACTIVE["write"]: 0}, "subjectId": self._did}
        data = await self._api.res_write(payload)
        if str(data.get("code")) != "0":
            raise Exception(f"Aqara API error: {data}")
        await self.coordinator.async_request_refresh()
