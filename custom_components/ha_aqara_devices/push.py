from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import logging
import time
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AqaraApi
from .bridge_specs import (
    FP2_GROUP_SPEC_MAPS,
    FP2_SUBSCRIPTION_RESOURCE_IDS,
    FP300_GROUP_SPEC_MAPS,
    FP300_SUBSCRIPTION_RESOURCE_IDS,
    GESTURE_RESOURCE_ID,
    G3_GESTURE_VALUE_MAP,
    G3_RESOURCE_SPEC_MAP,
    G3_SUBSCRIPTION_RESOURCE_IDS,
    M3_RESOURCE_SPEC_MAP,
    M3_SUBSCRIPTION_RESOURCE_IDS,
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
        self._listen_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._started = False

    async def async_start(self) -> None:
        if self._started:
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
        subscriptions: list[dict[str, Any]] = []

        for did in self._cameras:
            subscriptions.append({"subjectId": did, "resourceIds": G3_SUBSCRIPTION_RESOURCE_IDS})
        for did in self._hubs_m3:
            subscriptions.append({"subjectId": did, "resourceIds": M3_SUBSCRIPTION_RESOURCE_IDS})
        for did, device in self._presence_devices.items():
            model = str(device.get("model") or "")
            if model == FP2_MODEL:
                resource_ids = FP2_SUBSCRIPTION_RESOURCE_IDS
            elif model == FP300_MODEL:
                resource_ids = FP300_SUBSCRIPTION_RESOURCE_IDS
            else:
                continue
            subscriptions.append({"subjectId": did, "resourceIds": resource_ids})

        if not subscriptions:
            return

        response = await self._api.subscribe_resources(subscriptions)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to subscribe bridge resources: {response}")
        _LOGGER.info("Subscribed Aqara bridge resources for %s device(s)", len(subscriptions))

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
        if event_name in (None, "", "ready", "heartbeat") or not data_lines:
            return

        payload = json.loads("\n".join(data_lines))
        if not isinstance(payload, dict) or payload.get("type") != "resource_report":
            return
        await self._handle_message(payload)

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        did = str(payload.get("subjectId") or "")
        if not did:
            return
        if int(payload.get("statusCode", 0) or 0) != 0:
            return

        resource_id = str(payload.get("resourceId") or "")
        if not resource_id:
            return

        if did in self._cameras:
            await self._handle_g3_message(did, resource_id, payload.get("value"))
            return

        if did in self._hubs_m3:
            await self._handle_shared_device_message(
                did,
                resource_id,
                payload.get("value"),
                self._m3_coordinators,
                self._m3_state,
                M3_RESOURCE_SPEC_MAP,
                apply_scale=True,
            )
            return

        device = self._presence_devices.get(did)
        if device is None:
            return
        model = str(device.get("model") or "")
        if model == FP2_MODEL:
            await self._handle_grouped_presence_message(did, resource_id, payload.get("value"), FP2_GROUP_SPEC_MAPS)
        elif model == FP300_MODEL:
            await self._handle_grouped_presence_message(did, resource_id, payload.get("value"), FP300_GROUP_SPEC_MAPS)

    async def _handle_g3_message(self, did: str, resource_id: str, value: Any) -> None:
        if resource_id == GESTURE_RESOURCE_ID:
            gesture_key = G3_GESTURE_VALUE_MAP.get(str(value))
            if gesture_key is None:
                return
            coordinator = self._camera_coordinators.get(did)
            if coordinator is None:
                return
            state = dict(self._camera_state.get(did) or coordinator.data or {})
            state[gesture_key] = time.time()
            self._camera_state[did] = state
            coordinator.async_set_updated_data(state)
            return

        await self._handle_shared_device_message(
            did,
            resource_id,
            value,
            self._camera_coordinators,
            self._camera_state,
            G3_RESOURCE_SPEC_MAP,
            apply_scale=True,
        )

    async def _handle_shared_device_message(
        self,
        did: str,
        resource_id: str,
        value: Any,
        coordinators: dict[str, DataUpdateCoordinator],
        cache: dict[str, dict[str, Any]],
        resource_specs: dict[str, dict[str, Any]],
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

        state = dict(cache.get(did) or coordinator.data or {})
        state[key] = coerce_spec_value(spec, value, apply_scale=apply_scale)
        cache[did] = state
        coordinator.async_set_updated_data(state)

    async def _handle_grouped_presence_message(
        self,
        did: str,
        resource_id: str,
        value: Any,
        group_spec_maps: dict[str, dict[str, dict[str, Any]]],
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

            group_state_cache = self._presence_state.setdefault(did, {}).setdefault(group, {})
            coordinator_state = coordinator.data if isinstance(coordinator.data, dict) and coordinator.data else None
            state = dict(coordinator_state or group_state_cache or {})
            state[key] = coerce_spec_value(spec, value, apply_scale=False)
            self._presence_state[did][group] = state
            coordinator.async_set_updated_data(state)
            return
