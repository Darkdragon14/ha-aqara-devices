from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import hashlib
import json
import logging
import time
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import BRIDGE_SANITY_INTERVAL_SECONDS

from .api import AqaraApi, AqaraAuthError
from .bridge_specs import (
    A100_PRO_RESOURCE_SPEC_MAP,
    ACN002_RESOURCE_SPEC_MAP,
    FP2_GROUP_SPEC_MAPS,
    FP300_GROUP_SPEC_MAPS,
    G2H_PRO_RESOURCE_SPEC_MAP,
    G4_RESOURCE_SPEC_MAP,
    GESTURE_RESOURCE_ID,
    G3_GESTURE_VALUE_MAP,
    G3_RESOURCE_SPEC_MAP,
    M100_RESOURCE_SPEC_MAP,
    M200_RESOURCE_SPEC_MAP,
    M3_RESOURCE_SPEC_MAP,
    coerce_spec_value,
    g410_resource_spec_map_for_model,
    spec_event_time_key,
    spec_event_token_key,
    spec_state_key,
)
from .const import FP2_MODEL, FP300_MODEL

_LOGGER = logging.getLogger(__name__)
_EVENT_DEDUP_CACHE_SIZE = 256


class AqaraBridgeNotReady(RuntimeError):
    """Raised when the bridge HTTP API is reachable but not ready for push updates."""


class AqaraBridgePushManager:
    def __init__(
        self,
        hass,
        session: ClientSession,
        api: AqaraApi,
        bridge_url: str,
        bridge_token: str,
        cameras: list[dict[str, Any]],
        g2h_pro_cameras: list[dict[str, Any]],
        g410_doorbells: list[dict[str, Any]],
        g4_doorbells: list[dict[str, Any]],
        hubs_m3: list[dict[str, Any]],
        hubs_m100: list[dict[str, Any]],
        hubs_m200: list[dict[str, Any]],
        a100_pro_locks: list[dict[str, Any]],
        acn002_locks: list[dict[str, Any]],
        presence_devices: list[dict[str, Any]],
        child_devices: list[dict[str, Any]],
        camera_coordinators: dict[str, DataUpdateCoordinator],
        g2h_pro_coordinators: dict[str, DataUpdateCoordinator],
        g410_coordinators: dict[str, DataUpdateCoordinator],
        g4_coordinators: dict[str, DataUpdateCoordinator],
        m3_coordinators: dict[str, DataUpdateCoordinator],
        m100_coordinators: dict[str, DataUpdateCoordinator],
        m200_coordinators: dict[str, DataUpdateCoordinator],
        a100_pro_coordinators: dict[str, DataUpdateCoordinator],
        acn002_coordinators: dict[str, DataUpdateCoordinator],
        presence_coordinators: dict[str, dict[str, DataUpdateCoordinator]],
        child_coordinators: dict[str, DataUpdateCoordinator],
        child_resource_specs: dict[str, dict[str, dict[str, Any]]],
        child_polling_dids: set[str],
        subscriptions: list[dict[str, Any]],
    ) -> None:
        self._hass = hass
        self._session = session
        self._api = api
        self._bridge_url = bridge_url.rstrip("/")
        self._bridge_token = bridge_token
        self._camera_coordinators = camera_coordinators
        self._g2h_pro_coordinators = g2h_pro_coordinators
        self._g410_coordinators = g410_coordinators
        self._g4_coordinators = g4_coordinators
        self._m3_coordinators = m3_coordinators
        self._m100_coordinators = m100_coordinators
        self._m200_coordinators = m200_coordinators
        self._a100_pro_coordinators = a100_pro_coordinators
        self._acn002_coordinators = acn002_coordinators
        self._presence_coordinators = presence_coordinators
        self._child_coordinators = child_coordinators
        self._child_resource_specs = child_resource_specs
        self._child_polling_dids = child_polling_dids
        self._cameras = {device["did"]: device for device in cameras}
        self._g2h_pro_cameras = {device["did"]: device for device in g2h_pro_cameras}
        self._g410_doorbells = {device["did"]: device for device in g410_doorbells}
        self._g4_doorbells = {device["did"]: device for device in g4_doorbells}
        self._hubs_m3 = {device["did"]: device for device in hubs_m3}
        self._hubs_m100 = {device["did"]: device for device in hubs_m100}
        self._hubs_m200 = {device["did"]: device for device in hubs_m200}
        self._a100_pro_locks = {device["did"]: device for device in a100_pro_locks}
        self._acn002_locks = {device["did"]: device for device in acn002_locks}
        self._presence_devices = {device["did"]: device for device in presence_devices}
        self._child_devices = {device["did"]: device for device in child_devices}
        self._camera_state: dict[str, dict[str, Any]] = {did: {} for did in self._cameras}
        self._g2h_pro_state: dict[str, dict[str, Any]] = {did: {} for did in self._g2h_pro_cameras}
        self._g410_state: dict[str, dict[str, Any]] = {did: {} for did in self._g410_doorbells}
        self._g4_state: dict[str, dict[str, Any]] = {did: {} for did in self._g4_doorbells}
        self._m3_state: dict[str, dict[str, Any]] = {did: {} for did in self._hubs_m3}
        self._m100_state: dict[str, dict[str, Any]] = {did: {} for did in self._hubs_m100}
        self._m200_state: dict[str, dict[str, Any]] = {did: {} for did in self._hubs_m200}
        self._a100_pro_state: dict[str, dict[str, Any]] = {did: {} for did in self._a100_pro_locks}
        self._acn002_state: dict[str, dict[str, Any]] = {did: {} for did in self._acn002_locks}
        self._presence_state: dict[str, dict[str, dict[str, Any]]] = {
            did: {group: {} for group in coordinators}
            for did, coordinators in presence_coordinators.items()
        }
        self._child_state: dict[str, dict[str, Any]] = {did: {} for did in self._child_devices}
        self._subscriptions = self._normalize_subscriptions(subscriptions)
        self._listen_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._subscribed = False
        self._started = False
        self._sse_connected: bool | None = None
        self._event_id = 0
        self._seen_event_ids: dict[tuple[str, str], dict[int, None]] = {}

    @staticmethod
    def _normalize_subscriptions(subscriptions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for subscription in subscriptions:
            subject_id = str(subscription.get("subjectId") or "").strip()
            if not subject_id:
                continue
            normalized = merged.setdefault(subject_id, {"resourceIds": {}, "attach": ""})
            resource_map = normalized["resourceIds"]
            for resource_id in subscription.get("resourceIds") or []:
                normalized_resource = str(resource_id or "").strip()
                if normalized_resource:
                    resource_map[normalized_resource] = None
            attach = str(subscription.get("attach") or "").strip()
            if attach:
                normalized["attach"] = attach

        result: list[dict[str, Any]] = []
        for subject_id, normalized in merged.items():
            resource_ids = list(normalized["resourceIds"])
            if not resource_ids:
                continue
            item = {"subjectId": subject_id, "resourceIds": resource_ids}
            if normalized["attach"]:
                item["attach"] = normalized["attach"]
            result.append(item)
        return result

    def _subscription_resource_count(self) -> int:
        return sum(len(subscription["resourceIds"]) for subscription in self._subscriptions)

    def _all_coordinators(self):
        """Yield every coordinator managed by this push manager."""
        yield from self._camera_coordinators.values()
        yield from self._g2h_pro_coordinators.values()
        yield from self._g410_coordinators.values()
        yield from self._g4_coordinators.values()
        yield from self._m3_coordinators.values()
        yield from self._m100_coordinators.values()
        yield from self._m200_coordinators.values()
        yield from self._a100_pro_coordinators.values()
        yield from self._acn002_coordinators.values()
        yield from self._child_coordinators.values()
        for groups in self._presence_coordinators.values():
            yield from groups.values()

    def _set_sse_connected(self, connected: bool) -> None:
        """Use polling as fallback while retaining it for non-reportable children."""
        if self._sse_connected == connected:
            return

        interval = timedelta(seconds=BRIDGE_SANITY_INTERVAL_SECONDS)
        for coordinator in self._all_coordinators():
            was_disabled = coordinator.update_interval is None
            coordinator.update_interval = None if connected else interval
            if not connected and was_disabled:
                self._hass.async_create_task(coordinator.async_request_refresh())
        for did, coordinator in self._child_coordinators.items():
            if did in self._child_polling_dids:
                coordinator.update_interval = interval
        self._sse_connected = connected
        _LOGGER.info(
            "Aqara bridge SSE %s; polling fallback %s and %s child device(s) remain polled",
            "connected" if connected else "disconnected",
            "disabled" if connected else "enabled",
            len(self._child_polling_dids),
        )

    async def async_start(self) -> None:
        if self._started:
            return

        if not self._subscriptions:
            _LOGGER.info("No active Aqara bridge subscriptions for enabled entities; skipping SSE startup")
            self._started = True
            return

        self._set_sse_connected(False)
        await self._api.ensure_valid_access_token()
        await self._check_health()
        await self._subscribe_all_resources()

        self._stop_event.clear()
        self._connected_event.clear()
        if self._listen_task is None or self._listen_task.done():
            self._listen_task = self._hass.async_create_background_task(
                self._listen_loop(),
                "Aqara bridge SSE listener",
            )
        _LOGGER.info(
            "Aqara bridge SSE listener started; polling fallback remains active until connected"
        )
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
            status = str(payload.get("status") or "").strip().lower()
            rocketmq_started_value = payload.get("rocketmqStarted")
            rocketmq_started = rocketmq_started_value is True or str(rocketmq_started_value).lower() == "true"
            if status != "up" or not rocketmq_started:
                raise AqaraBridgeNotReady(
                    "Aqara bridge RocketMQ consumer is not ready "
                    f"(status={payload.get('status')}, rocketmqStarted={payload.get('rocketmqStarted')}, "
                    f"lastError={payload.get('lastError')})"
                )
            _LOGGER.info(
                "Aqara bridge health OK: status=%s rocketmq_started=%s nameserver=%s last_error=%s",
                payload.get("status"),
                rocketmq_started,
                payload.get("nameserver"),
                payload.get("lastError"),
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
        _LOGGER.debug("Aqara bridge subscription payload: %s", self._subscriptions)

    async def _unsubscribe_all_resources(self) -> None:
        if not self._subscriptions:
            return

        unsubscribe_payload = [
            {
                "subjectId": subscription["subjectId"],
                "resourceIds": subscription["resourceIds"],
            }
            for subscription in self._subscriptions
        ]
        response = await self._api.unsubscribe_resources(unsubscribe_payload)
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
                was_connected = self._connected_event.is_set()
                if was_connected:
                    reconnect_delay = 1.0
                if not self._stop_event.is_set():
                    _LOGGER.warning(
                        "Aqara bridge SSE stream closed; retrying in %.0f seconds",
                        reconnect_delay,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as err:
                if self._stop_event.is_set():
                    break
                _LOGGER.warning(
                    "Aqara bridge SSE connection failed; retrying in %.0f seconds: %s",
                    reconnect_delay,
                    err,
                )

            self._connected_event.clear()
            if self._stop_event.is_set():
                break

            # Re-enable polling before waiting for the SSE reconnect.
            self._set_sse_connected(False)

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
            self._set_sse_connected(True)
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
                if self._is_event_occurrence(raw_event):
                    self._flush_pending_updates(pending_updates)

        self._flush_pending_updates(pending_updates)

    @staticmethod
    def _flush_pending_updates(
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        for coordinator, state in pending_updates.values():
            coordinator.async_set_updated_data(dict(state))
        pending_updates.clear()

    def _is_event_occurrence(self, payload: dict[str, Any]) -> bool:
        did = str(payload.get("subjectId") or "")
        resource_id = str(payload.get("resourceId") or "")
        if did in self._cameras and resource_id == GESTURE_RESOURCE_ID:
            return True
        if did in self._cameras:
            spec = G3_RESOURCE_SPEC_MAP.get(resource_id)
        elif did in self._g410_doorbells:
            model = str(self._g410_doorbells[did].get("model") or "")
            spec = g410_resource_spec_map_for_model(model).get(resource_id)
        elif did in self._g4_doorbells:
            spec = G4_RESOURCE_SPEC_MAP.get(resource_id)
        else:
            return False
        return bool(spec and (spec.get("value_type") == "event" or spec.get("event_occurrence")))

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

        if did in self._g2h_pro_cameras:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._g2h_pro_coordinators,
                self._g2h_pro_state,
                G2H_PRO_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        if did in self._g410_doorbells:
            model = str(self._g410_doorbells[did].get("model") or "")
            resource_spec_map = g410_resource_spec_map_for_model(model)
            value_hash = hashlib.sha256(str(payload.get("value")).encode()).hexdigest()[:12]
            _LOGGER.debug(
                "G410 bridge event: payloadType=%s subjectId=%s resourceId=%s valueHash=%s time=%r hasMsgId=%s",
                payload_type,
                did,
                resource_id,
                value_hash,
                payload.get("time"),
                bool(payload.get("msgId")),
            )
            if resource_id not in resource_spec_map:
                _LOGGER.debug(
                    "Unknown G410 event: subjectId=%s resourceId=%s valueHash=%s",
                    did,
                    resource_id,
                    value_hash,
                )
                return
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._g410_coordinators,
                self._g410_state,
                resource_spec_map,
                pending_updates,
                apply_scale=True,
                event_payload=payload,
            )
            return

        if did in self._g4_doorbells:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._g4_coordinators,
                self._g4_state,
                G4_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
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

        if did in self._hubs_m100:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._m100_coordinators,
                self._m100_state,
                M100_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        if did in self._hubs_m200:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._m200_coordinators,
                self._m200_state,
                M200_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        if did in self._a100_pro_locks:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._a100_pro_coordinators,
                self._a100_pro_state,
                A100_PRO_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        if did in self._acn002_locks:
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._acn002_coordinators,
                self._acn002_state,
                ACN002_RESOURCE_SPEC_MAP,
                pending_updates,
                apply_scale=True,
            )
            return

        if did in self._child_devices and did in self._child_resource_specs:
            if resource_id not in self._child_resource_specs[did]:
                _LOGGER.debug(
                    "Unknown Aqara child event: subjectId=%s resourceId=%s attach=%r",
                    did,
                    resource_id,
                    payload.get("attach"),
                )
                return
            self._handle_shared_device_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                self._child_coordinators,
                self._child_state,
                self._child_resource_specs.get(did, {}),
                pending_updates,
                apply_scale=False,
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

    def _next_event_id(self) -> int:
        self._event_id = max(self._event_id + 1, time.time_ns())
        return self._event_id

    def _event_occurrence_id(
        self,
        payload: dict[str, Any] | None,
        did: str,
        resource_id: str,
    ) -> int | None:
        if payload is not None:
            msg_id = str(payload.get("msgId") or "")
            if msg_id:
                event_time = str(payload.get("time") or "")
                digest = hashlib.sha256(f"{msg_id}|{event_time}|{resource_id}".encode()).digest()
                event_id = int.from_bytes(digest[:8], "big") or 1
                seen_ids = self._seen_event_ids.setdefault((did, resource_id), {})
                if event_id in seen_ids:
                    return None
                seen_ids[event_id] = None
                if len(seen_ids) > _EVENT_DEDUP_CACHE_SIZE:
                    seen_ids.pop(next(iter(seen_ids)))
                return event_id
        return self._next_event_id()

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
        # The local bridge's SSE "snapshot" is a replay of recent events, not a
        # complete state dump. Merge it into the existing coordinator data so
        # fields missing from the replay do not regress to unknown.
        state = dict(cached_state or {})
        if isinstance(coordinator.data, dict):
            state.update(coordinator.data)
        return state

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
        event_payload: dict[str, Any] | None = None,
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

        is_binary_event = spec.get("value_type") == "event"
        is_event_occurrence = is_binary_event or spec.get("event_occurrence", False)
        if is_event_occurrence and payload_type == "snapshot":
            return

        if is_binary_event:
            if new_value != 1:
                return
            event_id = self._event_occurrence_id(event_payload, did, resource_id)
            if event_id is None:
                return
            state[key] = event_id
        elif spec.get("event_occurrence", False):
            event_id = self._event_occurrence_id(event_payload, did, resource_id)
            if event_id is None:
                return
            state[key] = new_value
            state[spec_event_token_key(spec)] = event_id
            event_time_key = spec_event_time_key(spec)
            if event_payload is not None and event_payload.get("time") is not None:
                state[event_time_key] = event_payload["time"]
            else:
                state.pop(event_time_key, None)
        elif key in state and state[key] == new_value:
            return
        else:
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
