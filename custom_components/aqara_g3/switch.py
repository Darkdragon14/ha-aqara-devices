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
    did = data["did"]

    async def _async_update_video_data():
        try:
            # Fetch latest set_video value (0/1)
            return await api.get_camera_active(did)
        except Exception as e:
            # Never raise ConfigEntryNotReady from a platform; let the coordinator handle retries
            raise UpdateFailed(str(e)) from e
        
    async def _async_update_detect_human_data():
        try:
            # Fetch latest set_video value (0/1)
            return await api.get_detect_human_active(did)
        except Exception as e:
            # Never raise ConfigEntryNotReady from a platform; let the coordinator handle retries
            raise UpdateFailed(str(e)) from e

    coordinator_video = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aqara_g3__camera_active",
        update_method=_async_update_video_data,
        update_interval=timedelta(seconds=1),
    )

    coordinator_detect_human = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aqara_g3__detect_human_active",
        update_method=_async_update_detect_human_data,
        update_interval=timedelta(seconds=1),
    )

    videoSwitch = AqaraG3VideoSwitch(coordinator_video, did, api)
    humanSwitch = AqaraG3DetectHumanSwitch(coordinator_detect_human, did, api)

    # Do NOT call async_config_entry_first_refresh() here to avoid bubbling setup errors
    async_add_entities([videoSwitch, humanSwitch], True)

    # Kick off the first refresh in the background; errors will be logged by the coordinator
    hass.async_create_task(coordinator_video.async_request_refresh())
    hass.async_create_task(coordinator_detect_human.async_request_refresh())