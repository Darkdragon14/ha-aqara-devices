from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import AqaraApi
from .const import DOMAIN, U200_DEVICE_LABEL
from .device_info import build_device_info
from .u200 import U200_DOOR_STATE_LABELS, U200_LOCK_STATE_LABELS, U200_LOCK_STATE_LOCKED, U200_LOCK_STATE_UNLOCKED


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    api: AqaraApi = data["api"]
    u200_locks: list[dict[str, Any]] = data.get("u200_locks", [])
    u200_coordinators: dict[str, DataUpdateCoordinator] = data.get("u200_coordinators", {})

    entities: list[LockEntity] = []
    for lock in u200_locks:
        did = lock["did"]
        coordinator = u200_coordinators.get(did)
        if coordinator is None:
            continue
        entities.append(
            AqaraU200Lock(
                coordinator,
                api,
                did,
                lock["deviceName"],
                lock["model"],
            )
        )

    async_add_entities(entities)


class AqaraU200Lock(CoordinatorEntity, LockEntity):
    _attr_has_entity_name = True
    _attr_name = "Lock"

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
        self._attr_unique_id = f"{did}_lock"

    @property
    def device_info(self):
        return build_device_info(self._did, self._device_name, self._model, U200_DEVICE_LABEL)

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return super().available and data.get("reachable") is not False

    @property
    def is_locked(self) -> bool | None:
        lock_state = self._state_value("lock_state")
        if lock_state == U200_LOCK_STATE_LOCKED:
            return True
        if lock_state in U200_LOCK_STATE_UNLOCKED:
            return False
        return None

    @property
    def is_jammed(self) -> bool:
        return self._state_value("lock_state") == "0" or self._state_value("door_state") == "2"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lock_state = self._state_value("lock_state")
        door_state = self._state_value("door_state")
        return {
            "lock_state": U200_LOCK_STATE_LABELS.get(lock_state, lock_state),
            "door_state": U200_DOOR_STATE_LABELS.get(door_state, door_state),
            "rechargeable": (self.coordinator.data or {}).get("rechargeable"),
        }

    def _state_value(self, key: str) -> str | None:
        value = (self.coordinator.data or {}).get(key)
        if value is None:
            return None
        return str(value)

    async def async_lock(self, **kwargs: Any) -> None:
        await self._api.set_u200_locked(self._did, True)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self._api.set_u200_locked(self._did, False)
        await self.coordinator.async_request_refresh()
