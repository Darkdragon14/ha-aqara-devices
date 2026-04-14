from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import json
import logging
import time
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import BRIDGE_SANITY_INTERVAL_SECONDS

from .api import AqaraApi, AqaraAuthError
from .bridge_specs import (
    FP2_GROUP_SPEC_MAPS,
    FP300_GROUP_SPEC_MAPS,
    GESTURE_RESOURCE_ID,
    G3_GESTURE_VALUE_MAP,
    G3_RESOURCE_SPEC_MAP,
    M3_RESOURCE_SPEC_MAP,
    coerce_spec_value,
    spec_state_key,
)
from .const import FP2_MODEL, FP300_MODEL

_LOGGER = logging.getLogger(__name__)


class AqaraBridgePushManager:
    def __init__(
        self,
        hass,
        session: ClientSession,
        api: AqaraApi,
        bridge_url: str,
        bridge_token: str,
        cameras: list[dict[str, Any]],
        hubs_m3: list[dict[str, Any]],
        presence_devices: list[dict[str, Any]],
        camera_coordinators: dict[str, DataUpdateCoordinator],
        m3_coordinators: dict[str, DataUpdateCoordinator],
        presence_coordinators: dict[str, dict[str, DataUpdateCoordinator]],
        subscriptions: list[dict[str, Any]],
    ) -> None:
        self._hass = hass
        self._session = session
        self._api = api
        self._bridge_url = bridge_url.rstrip("/")
        self._bridge_token = bridge_token
        self._camera_coordinators = camera_coordinators
        self._m3_coordinators = m3_coordinators
        self._presence_coordinators = presence_coordinators
        self._cameras = {device["did"]: device for device in cameras}
        self._hubs_m3 = {device["did"]: device for device in hubs_m3}
        self._presence_devices = {device["did"]: device for device in presence_devices}
        self._camera_state: dict[str, dict[str, Any]] = {did: {} for did in self._cameras}
        self._m3_state: dict[str, dict[str, Any]] = {did: {} for did in self._hubs_m3}
        self._presence_state: dict[str, dict[str, dict[str, Any]]] = {
            did: {group: {} for group in coordinators}
            for did, coordinators in presence_coordinators.items()
        }
        self._subscriptions = self._normalize_subscriptions(subscriptions)
        self._listen_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._subscribed = False
        self._started = False

    @staticmethod
    def _normalize_subscriptions(subscriptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, None]] = {}
        for subscription in subscriptions:
            subject_id = str(subscription.get("subjectId") or "").strip()
            if not subject_id:
                continue
            resource_map = merged.setdefault(subject_id, {})
            for resource_id in subscription.get("resourceIds") or []:
                normalized_resource = str(resource_id or "").strip()
                if normalized_resource:
                    resource_map[normalized_resource] = None
        return [
            {"subjectId": subject_id, "resourceIds": list(resource_map)}
            for subject_id, resource_map in merged.items()
            if resource_map
        ]

    def _subscription_resource_count(self) -> int:
        return sum(len(subscription["resourceIds"]) for subscription in self._subscriptions)

    def _all_coordinators(self):
        """Yield every coordinator managed by this push manager."""
        yield from self._camera_coordinators.values()
        yield from self._m3_coordinators.values()
        for groups in self._presence_coordinators.values():
            yield from groups.values()

    def _set_polling_enabled(self, enabled: bool) -> None:
        """Toggle coordinator polling based on bridge SSE health.

        When the bridge SSE stream is connected, polling is disabled because
        push delivers all resource updates in real time.  When SSE drops,
        polling is re-enabled as an automatic fallback.
        """
        interval = timedelta(seconds=BRIDGE_SANITY_INTERVAL_SECONDS) if enabled else None
        for coordinator in self._all_coordinators():
            coordinator.update_interval = interval
        _LOGGER.debug("Coordinator polling %s", "enabled" if enabled else "disabled")

    async def async_start(self) -> None:
        if self._started:
            return

        if not self._subscriptions:
            _LOGGER.info("No active Aqara bridge subscriptions for enabled entities; skipping SSE startup")
            self._started = True
            return

        await self._api.ensure_valid_access_token()
        await self._check_health()

        self._stop_event.clear()
        self._listen_task = self._hass.async_create_task(self._listen_loop())
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=15)
        except TimeoutError as err:
            await self.async_stop()
            raise RuntimeError("Timed out connecting to Aqara bridge SSE stream") from err

        await self._subscribe_all_resources()
        self._started = True

    async def async_stop(self) -> None:
        self._stop_event.set()
        self._connected_event.clear()

        if self._subscribed:
            try:
                await self._unsubscribe_all_resources()
            except AqaraAuthError as err:
                _LOGGER.warning("Aqara bridge unsubscribe skipped because authentication failed: %s", err)
            except Exception as err:
                _LOGGER.warning("Aqara bridge unsubscribe failed during shutdown: %s", err)
            finally:
                self._subscribed = False

        task = self._listen_task
        self._listen_task = None
        self._started = False
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _check_health(self) -> None:
        url = f"{self._bridge_url}/health"
        timeout = ClientTimeout(total=10)
        async with self._session.get(url, timeout=timeout) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Aqara bridge health check failed ({response.status}): {body}")

            payload = await response.json()
            _LOGGER.info(
                "Aqara bridge reachable: status=%s rocketmq_started=%s nameserver=%s",
                payload.get("status"),
                payload.get("rocketmqStarted"),
                payload.get("nameserver"),
            )

    async def _subscribe_all_resources(self) -> None:
        if not self._subscriptions:
            return

        response = await self._api.subscribe_resources(self._subscriptions)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to subscribe bridge resources: {response}")
        self._subscribed = True
        _LOGGER.info(
            "Subscribed Aqara bridge resources for %s device(s), %s resource(s)",
            len(self._subscriptions),
            self._subscription_resource_count(),
        )

    async def _unsubscribe_all_resources(self) -> None:
        if not self._subscriptions:
            return

        response = await self._api.unsubscribe_resources(self._subscriptions)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to unsubscribe bridge resources: {response}")
        _LOGGER.info(
            "Unsubscribed Aqara bridge resources for %s device(s), %s resource(s)",
            len(self._subscriptions),
            self._subscription_resource_count(),
        )

    async def _listen_loop(self) -> None:
        reconnect_delay = 1.0
        while not self._stop_event.is_set():
            self._connected_event.clear()
            try:
                await self._stream_events()
                if not self._stop_event.is_set():
                    _LOGGER.warning("Aqara bridge SSE stream closed, reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                if self._stop_event.is_set():
                    break
                _LOGGER.warning("Aqara bridge SSE connection failed: %s", err)

            # SSE disconnected - re-enable polling as fallback
            self._set_polling_enabled(True)

            if self._stop_event.is_set():
                break
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30.0)

    async def _stream_events(self) -> None:
        url = f"{self._bridge_url}/events"
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self._bridge_token}",
        }
        timeout = ClientTimeout(total=None, sock_connect=10, sock_read=None)
        async with self._session.get(url, headers=headers, timeout=timeout) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Aqara bridge events connection failed ({response.status}): {body}")

            self._connected_event.set()
            self._set_polling_enabled(False)
            _LOGGER.info("Connected to Aqara bridge SSE stream at %s", url)

            event_name: str | None = None
            data_lines: list[str] = []
            async for raw_line in response.content:
                if self._stop_event.is_set():
                    break

                line = raw_line.decode("utf-8").rstrip("\r\n")
                if not line:
                    await self._dispatch_sse_event(event_name, data_lines)
                    event_name = None
                    data_lines = []
                    continue

                if line.startswith(":"):
                    continue

                field, _, value = line.partition(":")
                value = value.lstrip(" ")
                if field == "event":
                    event_name = value
                elif field == "data":
                    data_lines.append(value)

            if event_name or data_lines:
                await self._dispatch_sse_event(event_name, data_lines)

    async def _dispatch_sse_event(self, event_name: str | None, data_lines: list[str]) -> None:
        if event_name in (None, "", "heartbeat") or not data_lines:
            return

        payload = json.loads("\n".join(data_lines))
        if not isinstance(payload, dict):
            return

        payload_type = str(payload.get("type") or event_name or "").strip().lower()
        if payload_type not in {"snapshot", "batch"}:
            return

        events = payload.get("events") or []
        if not isinstance(events, list):
            return

        self._apply_events(payload_type, events)

    def _apply_events(self, payload_type: str, events: list[Any]) -> None:
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]] = {}
        for raw_event in events:
            if isinstance(raw_event, dict):
                self._handle_message(payload_type, raw_event, pending_updates)

        for coordinator, state in pending_updates.values():
            coordinator.async_set_updated_data(dict(state))

    def _handle_message(
        self,
        payload_type: str,
        payload: dict[str, Any],
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        did = str(payload.get("subjectId") or "")
        if not did:
            return
        if int(payload.get("statusCode", 0) or 0) != 0:
            return

        resource_id = str(payload.get("resourceId") or "")
        if not resource_id:
            return

        if did in self._cameras:
            self._handle_g3_message(payload_type, did, resource_id, payload.get("value"), pending_updates)
            return

        if did in self._hubs_m3:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._m3_coordinators,
                self._m3_state,
                M3_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        device = self._presence_devices.get(did)
        if device is None:
            return
        model = str(device.get("model") or "")
        if model == FP2_MODEL:
            self._handle_grouped_presence_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                FP2_GROUP_SPEC_MAPS,
                pending_updates,
            )
        elif model == FP300_MODEL:
            self._handle_grouped_presence_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                FP300_GROUP_SPEC_MAPS,
                pending_updates,
            )

    def _queue_state_update(
        self,
        flush_key: tuple[str, ...],
        coordinator: DataUpdateCoordinator,
        state: dict[str, Any],
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        pending_updates[flush_key] = (coordinator, state)

    def _base_state(
        self,
        payload_type: str,
        flush_key: tuple[str, ...],
        cached_state: dict[str, Any] | None,
        coordinator: DataUpdateCoordinator,
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> dict[str, Any]:
        pending = pending_updates.get(flush_key)
        if pending is not None:
            _, pending_state = pending
            return dict(pending_state)
        if payload_type == "snapshot":
            return {}
        return dict(cached_state or coordinator.data or {})

    def _handle_g3_message(
        self,
        payload_type: str,
        did: str,
        resource_id: str,
        value: Any,
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        if resource_id == GESTURE_RESOURCE_ID:
            if payload_type == "snapshot":
                return
            gesture_key = G3_GESTURE_VALUE_MAP.get(str(value))
            if gesture_key is None:
                return
            coordinator = self._camera_coordinators.get(did)
            if coordinator is None:
                return
            flush_key = ("device", did, coordinator.name)
            state = self._base_state(
                payload_type,
                flush_key,
                self._camera_state.get(did),
                coordinator,
                pending_updates,
            )
            state[gesture_key] = time.time()
            self._camera_state[did] = state
            self._queue_state_update(flush_key, coordinator, state, pending_updates)
            return

        self._handle_shared_device_message(
            payload_type,
            did,
            resource_id,
            value,
            self._camera_coordinators,
            self._camera_state,
            G3_RESOURCE_SPEC_MAP,
            pending_updates,
            apply_scale=True,
        )

    def _handle_shared_device_message(
        self,
        payload_type: str,
        did: str,
        resource_id: str,
        value: Any,
        coordinators: dict[str, DataUpdateCoordinator],
        cache: dict[str, dict[str, Any]],
        resource_specs: dict[str, dict[str, Any]],
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
        *,
        apply_scale: bool,
    ) -> None:
        spec = resource_specs.get(resource_id)
        if spec is None:
            return

        key = spec_state_key(spec)
        if not key:
            return

        coordinator = coordinators.get(did)
        if coordinator is None:
            return

        flush_key = ("device", did, coordinator.name)
        state = self._base_state(
            payload_type,
            flush_key,
            cache.get(did),
            coordinator,
            pending_updates,
        )
        new_value = coerce_spec_value(spec, value, apply_scale=apply_scale)
        if key in state and state[key] == new_value:
            return
        state[key] = new_value
        cache[did] = state
        self._queue_state_update(flush_key, coordinator, state, pending_updates)

    def _handle_grouped_presence_message(
        self,
        payload_type: str,
        did: str,
        resource_id: str,
        value: Any,
        group_spec_maps: dict[str, dict[str, dict[str, Any]]],
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        for group, resource_specs in group_spec_maps.items():
            spec = resource_specs.get(resource_id)
            if spec is None:
                continue

            key = spec_state_key(spec)
            if not key:
                return

            coordinator = self._presence_coordinators.get(did, {}).get(group)
            if coordinator is None:
                return

            flush_key = ("presence", did, group)
            group_state_cache = self._presence_state.setdefault(did, {}).setdefault(group, {})
            coordinator_state = coordinator.data if isinstance(coordinator.data, dict) and coordinator.data else None
            state = self._base_state(
                payload_type,
                flush_key,
                group_state_cache or coordinator_state,
                coordinator,
                pending_updates,
            )
            new_value = coerce_spec_value(spec, value, apply_scale=False)
            if key in state and state[key] == new_value:
                return
            state[key] = new_value
            self._presence_state[did][group] = state
            self._queue_state_update(flush_key, coordinator, state, pending_updates)
            return
