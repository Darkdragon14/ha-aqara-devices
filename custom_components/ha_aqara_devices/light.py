from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .api import AqaraApi
from .const import DOMAIN, M1S_MODEL_LABELS
from .device_info import build_device_info
from .lights import M1S_LIGHT_ARGB, M1S_LIGHT_BRIGHTNESS, M1S_LIGHT_STATUS

BRIGHTNESS_SCALE = (1, 100)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    hubs_m1s: list[dict[str, Any]] = data.get("hubs_m1s", [])
    coordinators: dict[str, DataUpdateCoordinator] = data.get("m1s_coordinators", {})
    entities: list[LightEntity] = []

    for hub in hubs_m1s:
        did = str(hub["did"])
        coordinator = coordinators.get(did)
        if coordinator is None:
            continue
        entities.append(
            AqaraM1SNightLight(
                coordinator,
                api,
                did,
                str(hub["deviceName"]),
                str(hub["model"]),
            )
        )

    async_add_entities(entities)


class AqaraM1SNightLight(CoordinatorEntity, LightEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "night_light"
    _attr_icon = "mdi:lightbulb-night"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api: AqaraApi,
        did: str,
        device_name: str,
        model: str,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._did = did
        self._device_name = device_name
        self._model = model
        self._attr_unique_id = f"{did}_night_light"

    @property
    def device_info(self):
        return build_device_info(
            self._did,
            self._device_name,
            self._model,
            M1S_MODEL_LABELS[self._model],
        )

    @staticmethod
    def _int_value(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _brightness_percent(self) -> int | None:
        data = self.coordinator.data or {}
        value = self._int_value(data.get(M1S_LIGHT_BRIGHTNESS["inApp"]))
        if value is None:
            argb = self._int_value(data.get(M1S_LIGHT_ARGB["inApp"]))
            value = None if argb is None else (argb >> 24) & 0xFF
        if value is None or not 0 <= value <= 100:
            return None
        return value

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        status = self._int_value(data.get(M1S_LIGHT_STATUS["inApp"]))
        if status is None:
            return None
        brightness = self._brightness_percent()
        return status != 0 and brightness != 0

    @property
    def brightness(self) -> int | None:
        value = self._brightness_percent()
        if value is None or value == 0:
            return None
        return value_to_brightness(BRIGHTNESS_SCALE, value)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        data = self.coordinator.data or {}
        argb = self._int_value(data.get(M1S_LIGHT_ARGB["inApp"]))
        if argb is None:
            return None
        return ((argb >> 16) & 0xFF, (argb >> 8) & 0xFF, argb & 0xFF)

    async def async_turn_on(self, **kwargs: Any) -> None:
        requested_brightness = kwargs.get(ATTR_BRIGHTNESS)
        if requested_brightness == 0:
            await self.async_turn_off()
            return

        data: dict[str, int] = {M1S_LIGHT_STATUS["api"]: 1}
        brightness = self._brightness_percent()
        if requested_brightness is not None:
            brightness = round(brightness_to_value(BRIGHTNESS_SCALE, requested_brightness))
            brightness = max(1, min(100, brightness))
            data[M1S_LIGHT_BRIGHTNESS["api"]] = brightness
        elif brightness is None or brightness == 0:
            brightness = 100
            data[M1S_LIGHT_BRIGHTNESS["api"]] = brightness

        requested_rgb = kwargs.get(ATTR_RGB_COLOR)
        rgb = requested_rgb or self.rgb_color
        if requested_rgb is not None:
            if brightness is None or brightness == 0:
                brightness = 100
            data[M1S_LIGHT_BRIGHTNESS["api"]] = brightness
        if rgb is not None and (requested_rgb is not None or requested_brightness is not None):
            if brightness is None or brightness == 0:
                brightness = 100
            red, green, blue = (max(0, min(255, int(value))) for value in rgb)
            data[M1S_LIGHT_ARGB["api"]] = (
                (brightness << 24) | (red << 16) | (green << 8) | blue
            )

        await self._write(data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write({M1S_LIGHT_STATUS["api"]: 0})

    async def _write(self, data: dict[str, int]) -> None:
        response = await self._api.res_write({"subjectId": self._did, "data": data})
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Aqara API error: {response}")
        await self.coordinator.async_request_refresh()
