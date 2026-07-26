from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .camera_config import build_rtsp_stream_url, stream_config_for_did
from .const import (
    CONF_CAMERA_STREAMS,
    CONF_GO2RTC_PASSWORD,
    CONF_GO2RTC_RTSP_URL,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_USERNAME,
    CONF_STREAM_NAME,
    DATA_CAMERA_CANDIDATES,
    DOMAIN,
)
from .device_info import build_device_info
from .go2rtc_client import Go2RtcClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    candidates: list[dict[str, str]] = data.get(DATA_CAMERA_CANDIDATES, [])
    stream_options = entry.options.get(CONF_CAMERA_STREAMS, {})
    api_url = str(entry.options.get(CONF_GO2RTC_URL, "")).strip()
    rtsp_url = str(entry.options.get(CONF_GO2RTC_RTSP_URL, "")).strip()
    if not api_url or not rtsp_url:
        return

    client = Go2RtcClient(
        aiohttp_client.async_get_clientsession(hass),
        api_url,
        str(entry.options.get(CONF_GO2RTC_USERNAME, "")),
        str(entry.options.get(CONF_GO2RTC_PASSWORD, "")),
    )
    entities: list[AqaraGo2RtcCamera] = []
    for candidate in candidates:
        config = stream_config_for_did(stream_options, candidate["did"])
        if config is None:
            continue
        stream_url = build_rtsp_stream_url(rtsp_url, config[CONF_STREAM_NAME])
        if stream_url is None:
            _LOGGER.warning("Invalid go2rtc RTSP URL configured for Aqara camera %s", candidate["did"])
            continue
        entities.append(AqaraGo2RtcCamera(candidate, config[CONF_STREAM_NAME], stream_url, client))

    async_add_entities(entities)


class AqaraGo2RtcCamera(Camera):
    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_translation_key = "live_stream"

    def __init__(
        self,
        device: dict[str, str],
        stream_name: str,
        stream_url: str,
        client: Go2RtcClient,
    ) -> None:
        super().__init__()
        self._did = device["did"]
        self._device_name = device["deviceName"]
        self._model = device["model"]
        self._device_label = device["label"]
        self._stream_name = stream_name
        self._stream_url = stream_url
        self._client = client
        self._attr_unique_id = f"{self._did}_live_stream"

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"stream_name": self._stream_name, "model": self._model}

    async def stream_source(self) -> str | None:
        return self._stream_url

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        try:
            return await self._client.get_snapshot(self._stream_name, width, height)
        except Exception as err:
            _LOGGER.warning("Unable to capture go2rtc snapshot for Aqara camera %s: %s", self._did, err)
            return None
