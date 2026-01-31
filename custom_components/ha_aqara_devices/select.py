from __future__ import annotations
from datetime import timedelta
from typing import Any, Dict
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import AqaraApi
from .const import DOMAIN, M3_DEVICE_LABEL
from .device_info import build_device_info
from .selects import M3_SELECTS_DEF

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    hubs_m3: list[dict] = data.get("hubs_m3", [])

    entities: list[SelectEntity] = []

    for hub in hubs_m3:
        did = hub["did"]
        name = hub["deviceName"]
        model = hub["model"]

        async def _async_update_m3_data(did_local=did):
            try:
                return await api.get_device_states(did_local, M3_SELECTS_DEF)
            except Exception as e:
                raise UpdateFailed(str(e)) from e

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-hub-m3-select-{did}",
            update_method=_async_update_m3_data,
            update_interval=timedelta(seconds=1),
        )

        for select_def in M3_SELECTS_DEF:
            select = AqaraSelect(
                coordinator,
                api,
                did,
                name,
                select_def,
                model,
                M3_DEVICE_LABEL,
            )
            entities.append(select)

    async_add_entities(entities)


class AqaraSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api: AqaraApi,
        did: str,
        device_name: str,
        spec: Dict[str, Any],
        model: str,
        device_label: str,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._did = did
        self._device_name = device_name
        self._spec = spec
        self._model = model
        self._device_label = device_label

        self._attr_unique_id = f"{did}_{spec['inApp']}"
        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")

        option_pairs = spec.get("options", [])
        self._option_by_value = {value: label for value, label in option_pairs}
        self._value_by_option = {label: value for value, label in option_pairs}
        self._attr_options = [label for _, label in option_pairs]

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, self._device_label)

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        raw = data.get(self._spec["inApp"])
        if raw is None:
            return None
        option = self._option_by_value.get(raw)
        if option is not None:
            return option
        try:
            return self._option_by_value.get(int(raw))
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        value = self._value_by_option.get(option)
        if value is None:
            return
        payload = {
            "data": {
                self._spec["api"]: value
            },
            "subjectId": self._did,
        }
        resp = await self._api.res_write(payload)
        if str(resp.get("code")) != "0":
            raise Exception(f"Aqara API error: {resp}")
        await self.coordinator.async_request_refresh()
