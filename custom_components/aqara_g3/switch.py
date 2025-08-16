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

    async def _async_update_all_data():
        try:
            # Returns {"camera_active": 0/1, "detect_human_active": 0/1}
            return await api.get_device_states(did)
        except Exception as e:
            raise UpdateFailed(str(e)) from e

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="aqara_g3__states",
        update_method=_async_update_all_data,
        update_interval=timedelta(seconds=1),
    )

    videoSwitch = AqaraG3VideoSwitch(coordinator, did, api)
    humanSwitch = AqaraG3DetectHumanSwitch(coordinator, did, api)

    # Do NOT call async_config_entry_first_refresh() here to avoid bubbling setup errors
    async_add_entities([videoSwitch, humanSwitch], True)

    # Kick off the first refresh in the background; errors will be logged by the coordinator
    hass.async_create_task(coordinator.async_request_refresh())