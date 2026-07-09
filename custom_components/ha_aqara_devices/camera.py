from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .camera_config import build_rtsp_url, mask_rtsp_url, normalize_rtsp_camera_config, rtsp_config_for_did
from .const import (
    CONF_RTSP_CAMERAS,
    CONF_RTSP_HOST,
    CONF_RTSP_PATH,
    CONF_RTSP_PORT,
    DATA_RTSP_CANDIDATE_CAMERAS,
    DOMAIN,
)
from .device_info import build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    candidates: list[dict[str, str]] = data.get(DATA_RTSP_CANDIDATE_CAMERAS, [])
    camera_options = entry.options.get(CONF_RTSP_CAMERAS, {})
    entities: list[AqaraRtspCamera] = []

    for candidate in candidates:
        did = candidate["did"]
        rtsp_config = rtsp_config_for_did(camera_options, did)
        if rtsp_config is None:
            continue

        entities.append(
            AqaraRtspCamera(
                hass,
                candidate,
                rtsp_config,
            )
        )

    async_add_entities(entities)


class AqaraRtspCamera(Camera):
    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_translation_key = "live_stream"

    def __init__(
        self,
        hass: HomeAssistant,
        device: dict[str, str],
        rtsp_config: dict[str, Any],
    ) -> None:
        super().__init__()
        self.hass = hass
        self._did = device["did"]
        self._device_name = device["deviceName"]
        self._model = device["model"]
        self._device_label = device["label"]
        self._rtsp_config = normalize_rtsp_camera_config(rtsp_config)
        self._attr_unique_id = f"{self._did}_live_stream"

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "rtsp_host": self._rtsp_config[CONF_RTSP_HOST],
            "rtsp_port": self._rtsp_config[CONF_RTSP_PORT],
            "rtsp_path": self._rtsp_config[CONF_RTSP_PATH],
            "rtsp_url": mask_rtsp_url(self._rtsp_config),
            "model": self._model,
        }

    async def stream_source(self) -> str | None:
        return build_rtsp_url(self._rtsp_config)

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        rtsp_url = build_rtsp_url(self._rtsp_config)
        if rtsp_url is None:
            return None

        try:
            return await ffmpeg.async_get_image(
                self.hass,
                rtsp_url,
                width=width,
                height=height,
            )
        except Exception as err:
            _LOGGER.warning(
                "Unable to capture Aqara RTSP snapshot for %s from %s: %s",
                self._did,
                mask_rtsp_url(self._rtsp_config),
                err,
            )
            return None
