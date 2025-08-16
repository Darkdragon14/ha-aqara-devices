from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .api import AqaraApi
from .switches.AqaraG3VideoSwitch import AqaraG3VideoSwitch
from .switches.AqaraG3DetectHumanSwitch import AqaraG3DetectHumanSwitch

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    dids: list[str] = data["dids"]
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

        videoSwitch = AqaraG3VideoSwitch(coordinator, did, name, api)
        humanSwitch = AqaraG3DetectHumanSwitch(coordinator, did, name, api)

        entities.append(videoSwitch)
        entities.append(humanSwitch)

    async_add_entities(entities)