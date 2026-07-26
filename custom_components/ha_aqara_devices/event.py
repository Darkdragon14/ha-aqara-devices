from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .bridge_specs import spec_event_time_key, spec_event_token_key
from .const import DOMAIN, G410_DEVICE_LABEL
from .device_info import build_device_info
from .events import G410_EVENTS_DEF


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, DataUpdateCoordinator] = data.get("g410_coordinators", {})
    entities = []

    for doorbell in data.get("g410_doorbells", []):
        did = doorbell["did"]
        coordinator = coordinators.get(did)
        if coordinator is None:
            continue
        for spec in G410_EVENTS_DEF:
            entities.append(
                AqaraG410Event(
                    coordinator,
                    did,
                    doorbell["deviceName"],
                    doorbell["model"],
                    spec,
                )
            )

    async_add_entities(entities)


class AqaraG410Event(CoordinatorEntity, EventEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        did: str,
        device_name: str,
        model: str,
        spec: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._did = did
        self._device_name = device_name
        self._model = model
        self._spec = spec
        self._event_token_key = spec_event_token_key(spec)
        self._event_time_key = spec_event_time_key(spec)
        self._last_event_id: Any = None

        self._attr_translation_key = spec["translation_key"]
        self._attr_icon = spec["icon"]
        self._attr_unique_id = f"{did}_{spec['inApp']}"
        self._attr_event_types = [spec["event_type"]]

    @property
    def device_info(self):
        return build_device_info(
            self._did,
            self._device_name,
            self._model,
            G410_DEVICE_LABEL,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._last_event_id = (self.coordinator.data or {}).get(self._event_token_key)

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or {}
        event_id = data.get(self._event_token_key)
        if event_id is None or event_id == self._last_event_id:
            super()._handle_coordinator_update()
            return

        member_id = data.get(self._spec["key"])
        self._last_event_id = event_id
        if member_id is None:
            super()._handle_coordinator_update()
            return

        event_data: dict[str, Any] = {"member_id": str(member_id)}
        event_time = data.get(self._event_time_key)
        if event_time is not None:
            event_data["time"] = event_time
        self._trigger_event(self._spec["event_type"], event_data)
        self.async_write_ha_state()
