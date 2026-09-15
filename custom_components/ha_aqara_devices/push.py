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

from .const import BRIDGE_SANITY_INTERVAL_SECONDS, U200_INTERVAL_SECONDS

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
from .u200 import U200_TRAIT_CODE_PATH_MAP, coerce_u200_trait_value

_LOGGER = logging.getLogger(__name__)
_EVENT_DEDUP_CACHE_SIZE = 256
_SSE_READ_TIMEOUT_SECONDS = 45
_BRIDGE_HEALTH_INTERVAL_SECONDS = 30


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
        u200_coordinators: dict[str, DataUpdateCoordinator],
        trait_subscriptions: list[dict[str, Any]],
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
        self._u200_coordinators = u200_coordinators
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
        self._u200_state: dict[str, dict[str, Any]] = {did: {} for did in u200_coordinators}
        self._u200_push_versions: dict[str, dict[str, tuple[int, Any]]] = {}
        for did, coordinator in u200_coordinators.items():
            push_versions = getattr(coordinator, "_aqara_push_version_data", None)
            if not isinstance(push_versions, dict):
                push_versions = {}
                coordinator._aqara_push_version_data = push_versions
                coordinator._aqara_push_versions = (
                    lambda push_versions=push_versions: dict(push_versions)
                )
            self._u200_push_versions[did] = push_versions
        self._u200_push_generation = 0
        self._subscriptions = self._normalize_subscriptions(subscriptions)
        self._trait_subscriptions = trait_subscriptions
        self._listen_task: asyncio.Task[None] | None = None
        self._health_task: asyncio.Task[None] | None = None
        self._trait_retry_task: asyncio.Task[None] | None = None
        self._u200_reconciliation_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._resources_subscribed = False
        self._traits_subscribed = False
        self._bridge_supports_traits = False
        self._sse_read_timeout_seconds: float | None = None
        self._started = False
        self._sse_connected: bool | None = None
        self._bridge_healthy = False
        self._u200_push_active: bool | None = None
        self._u200_reconciled = False
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
        connected = connected and getattr(self, "_bridge_healthy", True)
        if not connected:
            self._u200_reconciled = False
            reconciliation_task = getattr(self, "_u200_reconciliation_task", None)
            self._u200_reconciliation_task = None
            if reconciliation_task is not None:
                reconciliation_task.cancel()
        u200_push_active = (
            connected
            and self._traits_subscribed
            and getattr(self, "_u200_reconciled", False)
        )
        if self._sse_connected == connected and self._u200_push_active == u200_push_active:
            return

        if not connected and self._u200_push_active:
            self._u200_state = {did: {} for did in self._u200_coordinators}

        interval = timedelta(seconds=BRIDGE_SANITY_INTERVAL_SECONDS)
        for coordinator in self._all_coordinators():
            was_disabled = coordinator.update_interval is None
            coordinator.update_interval = None if connected else interval
            if not connected and was_disabled:
                self._hass.async_create_task(coordinator.async_request_refresh())
        for did, coordinator in self._child_coordinators.items():
            if did in self._child_polling_dids:
                coordinator.update_interval = interval
        u200_interval = None if u200_push_active else timedelta(seconds=U200_INTERVAL_SECONDS)
        for coordinator in self._u200_coordinators.values():
            was_disabled = coordinator.update_interval is None
            coordinator.update_interval = u200_interval
            if u200_interval is None and not was_disabled and coordinator.data is not None:
                # async_refresh schedules from the interval it started with.
                # A manual update cancels that timer and observes the new None interval.
                coordinator.async_set_updated_data(coordinator.data)
            if u200_interval is not None and was_disabled:
                self._hass.async_create_task(coordinator.async_request_refresh())
        self._sse_connected = connected
        self._u200_push_active = u200_push_active
        _LOGGER.info(
            "Aqara bridge SSE %s; polling fallback %s, %s child device(s) and %s U200 device(s) remain polled",
            "connected" if connected else "disconnected",
            "disabled" if connected else "enabled",
            len(self._child_polling_dids),
            0 if u200_push_active else len(self._u200_coordinators),
        )

    async def _reconcile_u200_before_push(self) -> None:
        """Refresh U200 state before snapshots are ignored and polling is disabled."""
        if not getattr(self, "_traits_subscribed", False) or not getattr(
            self, "_u200_coordinators", {}
        ):
            self._u200_reconciled = True
            return

        coordinators = list(self._u200_coordinators.values())
        attempts_before = [
            getattr(coordinator, "_aqara_resilient_state", {}).get("network_attempts", 0)
            for coordinator in coordinators
        ]
        results = await asyncio.gather(
            *(coordinator.async_refresh() for coordinator in coordinators),
            return_exceptions=True,
        )
        self._u200_reconciled = all(
            not isinstance(result, BaseException)
            and isinstance(
                resilient_state := getattr(coordinator, "_aqara_resilient_state", None),
                dict,
            )
            and resilient_state.get("network_attempts", 0) > attempts
            and resilient_state.get("last_network_success") is True
            for coordinator, result, attempts in zip(
                coordinators, results, attempts_before, strict=True
            )
        )
        if not self._u200_reconciled:
            _LOGGER.warning(
                "Aqara U200 reconciliation failed; polling remains active while SSE is connected"
            )

    def _start_u200_reconciliation_retry(self) -> None:
        task = self._u200_reconciliation_task
        if task is None or task.done():
            self._u200_reconciliation_task = self._hass.async_create_background_task(
                self._u200_reconciliation_retry_loop(),
                "Aqara U200 reconciliation retry",
            )

    async def _u200_reconciliation_retry_loop(self) -> None:
        retry_delay = 30.0
        while self._sse_connected and self._traits_subscribed and not self._u200_reconciled:
            await asyncio.sleep(retry_delay)
            if not self._sse_connected or self._stop_event.is_set():
                return
            await self._reconcile_u200_before_push()
            if not self._sse_connected:
                return
            self._set_sse_connected(True)
            if self._u200_reconciled:
                return
            retry_delay = min(retry_delay * 2, 300.0)

    async def async_start(self) -> None:
        if self._started:
            return

        self._stop_event.clear()

        if not self._subscriptions and not self._trait_subscriptions:
            _LOGGER.info("No active Aqara bridge subscriptions for enabled entities; skipping SSE startup")
            self._started = True
            return

        self._set_sse_connected(False)
        await self._api.ensure_valid_access_token()
        await self._check_health()
        self._bridge_healthy = True
        await self._subscribe_all_resources()
        try:
            await self._subscribe_all_traits()
        except Exception as err:
            if not self._resources_subscribed:
                raise
            _LOGGER.warning(
                "Aqara trait subscription failed; U200 polling remains active and subscription will be retried: %s",
                err,
            )
            self._start_trait_subscription_retry()

        if not self._resources_subscribed and not self._traits_subscribed:
            _LOGGER.warning(
                "No subscriptions supported by this Aqara bridge; polling remains active"
            )
            self._started = True
            return

        self._connected_event.clear()
        if self._listen_task is None or self._listen_task.done():
            self._listen_task = self._hass.async_create_background_task(
                self._listen_loop(),
                "Aqara bridge SSE listener",
            )
        if self._health_task is None or self._health_task.done():
            self._health_task = self._hass.async_create_background_task(
                self._bridge_health_loop(),
                "Aqara bridge health monitor",
            )
        _LOGGER.info(
            "Aqara bridge SSE listener started; polling fallback remains active until connected"
        )
        self._started = True

    async def async_stop(self) -> None:
        self._stop_event.set()
        self._connected_event.clear()

        trait_retry_task = self._trait_retry_task
        self._trait_retry_task = None
        if trait_retry_task is not None:
            trait_retry_task.cancel()
            with suppress(asyncio.CancelledError):
                await trait_retry_task

        health_task = getattr(self, "_health_task", None)
        self._health_task = None
        if health_task is not None:
            health_task.cancel()
            with suppress(asyncio.CancelledError):
                await health_task

        reconciliation_task = getattr(self, "_u200_reconciliation_task", None)
        self._u200_reconciliation_task = None
        if reconciliation_task is not None:
            reconciliation_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconciliation_task

        if self._resources_subscribed:
            try:
                await self._unsubscribe_all_resources()
            except AqaraAuthError as err:
                _LOGGER.warning("Aqara bridge unsubscribe skipped because authentication failed: %s", err)
            except Exception as err:
                _LOGGER.warning("Aqara bridge unsubscribe failed during shutdown: %s", err)
            finally:
                self._resources_subscribed = False
        if self._traits_subscribed:
            try:
                await self._unsubscribe_all_traits()
            except AqaraAuthError as err:
                _LOGGER.warning("Aqara trait unsubscribe skipped because authentication failed: %s", err)
            except Exception as err:
                _LOGGER.warning("Aqara trait unsubscribe failed during shutdown: %s", err)
            finally:
                self._traits_subscribed = False

        task = self._listen_task
        self._listen_task = None
        self._started = False
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _check_health(self, *, log_success: bool = True) -> None:
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
            consumer_registered = payload.get("consumerRegistered")
            assigned_queue_count = payload.get("assignedQueueCount")
            queue_assignment_ready = assigned_queue_count is None
            try:
                if assigned_queue_count is not None:
                    queue_assignment_ready = int(assigned_queue_count) > 0
            except (TypeError, ValueError):
                queue_assignment_ready = False
            if (
                status != "up"
                or not rocketmq_started
                or consumer_registered is False
                or not queue_assignment_ready
            ):
                raise AqaraBridgeNotReady(
                    "Aqara bridge RocketMQ consumer is not ready "
                    f"(status={payload.get('status')}, rocketmqStarted={payload.get('rocketmqStarted')}, "
                    f"consumerRegistered={consumer_registered}, assignedQueueCount={assigned_queue_count}, "
                    f"lastError={payload.get('lastError')})"
                )
            if log_success:
                _LOGGER.info(
                    "Aqara bridge health OK: status=%s rocketmq_started=%s consumer_registered=%s "
                    "assigned_queue_count=%s raw_message_count=%s parsed_message_count=%s "
                    "published_event_count=%s ignored_message_count=%s processing_error_count=%s "
                    "last_raw_message_at=%s last_message_type=%s last_ignored_reason=%s "
                    "nameserver=%s last_error=%s",
                    payload.get("status"),
                    rocketmq_started,
                    consumer_registered,
                    assigned_queue_count,
                    payload.get("rawMessageCount"),
                    payload.get("parsedMessageCount"),
                    payload.get("publishedEventCount"),
                    payload.get("ignoredMessageCount"),
                    payload.get("processingErrorCount"),
                    payload.get("lastRawMessageAt"),
                    payload.get("lastMessageType"),
                    payload.get("lastIgnoredReason"),
                    payload.get("nameserver"),
                    payload.get("lastError"),
                )
            capabilities = payload.get("capabilities") or []
            self._bridge_supports_traits = (
                isinstance(capabilities, list) and "spec_report" in capabilities
            )
            if self._trait_subscriptions and not self._bridge_supports_traits:
                _LOGGER.warning(
                    "Aqara bridge does not advertise spec_report support; U200 polling remains active"
                )
            heartbeat_interval = payload.get("heartbeatIntervalSeconds")
            self._sse_read_timeout_seconds = None
            try:
                heartbeat_interval_seconds = float(heartbeat_interval)
            except (TypeError, ValueError):
                heartbeat_interval_seconds = 0
            if heartbeat_interval_seconds > 0:
                self._sse_read_timeout_seconds = max(
                    heartbeat_interval_seconds * 3,
                    _SSE_READ_TIMEOUT_SECONDS,
                )

    async def _bridge_health_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(_BRIDGE_HEALTH_INTERVAL_SECONDS)
            if self._stop_event.is_set() or not self._connected_event.is_set():
                continue

            try:
                await self._check_health(log_success=False)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._bridge_healthy = False
                if self._sse_connected:
                    _LOGGER.warning(
                        "Aqara bridge became unhealthy; polling fallback enabled: %s",
                        err,
                    )
                    self._set_sse_connected(False)
                continue

            if not self._sse_connected and self._connected_event.is_set():
                _LOGGER.info("Aqara bridge health recovered; reconciling before push resumes")
                await self._reconcile_u200_before_push()
                if self._connected_event.is_set():
                    self._bridge_healthy = True
                    self._set_sse_connected(True)
                    if not self._u200_reconciled:
                        self._start_u200_reconciliation_retry()

    async def _subscribe_all_resources(self) -> None:
        if not self._subscriptions:
            return

        response = await self._api.subscribe_resources(self._subscriptions)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to subscribe bridge resources: {response}")
        self._resources_subscribed = True
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

    async def _subscribe_all_traits(self) -> None:
        if not self._trait_subscriptions or not self._bridge_supports_traits:
            return

        response = await self._api.subscribe_traits(self._trait_subscriptions)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to subscribe Aqara traits: {response}")
        self._traits_subscribed = True
        _LOGGER.info(
            "Subscribed Aqara bridge traits for %s device(s), %s trait(s), request_id=%s",
            len(self._trait_subscriptions),
            sum(len(subscription["codePaths"]) for subscription in self._trait_subscriptions),
            response.get("requestId"),
        )
        _LOGGER.debug("Aqara bridge trait subscription payload: %s", self._trait_subscriptions)

    def _start_trait_subscription_retry(self) -> None:
        if self._trait_retry_task is None or self._trait_retry_task.done():
            self._trait_retry_task = self._hass.async_create_background_task(
                self._trait_subscription_retry_loop(),
                "Aqara trait subscription retry",
            )

    async def _trait_subscription_retry_loop(self) -> None:
        retry_delay = 30.0
        while not self._stop_event.is_set() and not self._traits_subscribed:
            await asyncio.sleep(retry_delay)
            if self._stop_event.is_set():
                return
            try:
                await self._api.ensure_valid_access_token()
                await self._subscribe_all_traits()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.warning(
                    "Aqara trait subscription retry failed; retrying in %.0f seconds: %s",
                    min(retry_delay * 2, 300.0),
                    err,
                )
                retry_delay = min(retry_delay * 2, 300.0)
                continue

            if self._sse_connected:
                await self._reconcile_u200_before_push()
                if self._sse_connected:
                    self._set_sse_connected(True)
                    if not self._u200_reconciled:
                        self._start_u200_reconciliation_retry()
            return

    async def _unsubscribe_all_traits(self) -> None:
        unsubscribe_payload = [
            {
                "deviceId": subscription["deviceId"],
                "codePaths": subscription["codePaths"],
            }
            for subscription in self._trait_subscriptions
        ]
        response = await self._api.unsubscribe_traits(unsubscribe_payload)
        if str(response.get("code")) != "0":
            raise RuntimeError(f"Failed to unsubscribe Aqara traits: {response}")
        _LOGGER.info(
            "Unsubscribed Aqara bridge traits for %s device(s)",
            len(unsubscribe_payload),
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
        timeout = ClientTimeout(
            total=None,
            sock_connect=10,
            sock_read=self._sse_read_timeout_seconds,
        )
        async with self._session.get(url, headers=headers, timeout=timeout) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Aqara bridge events connection failed ({response.status}): {body}")

            self._connected_event.set()
            await self._reconcile_u200_before_push()
            self._set_sse_connected(True)
            if not self._u200_reconciled:
                self._start_u200_reconciliation_retry()
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

        if str(payload.get("type") or "") == "spec_report":
            self._handle_u200_trait_message(
                payload_type,
                did,
                resource_id,
                payload.get("value"),
                pending_updates,
            )
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

    def _handle_u200_trait_message(
        self,
        payload_type: str,
        did: str,
        code_path: str,
        value: Any,
        pending_updates: dict[tuple[str, ...], tuple[DataUpdateCoordinator, dict[str, Any]]],
    ) -> None:
        if payload_type == "snapshot":
            return

        coordinator = self._u200_coordinators.get(did)
        spec = U200_TRAIT_CODE_PATH_MAP.get(code_path)
        if coordinator is None or spec is None:
            return

        flush_key = ("u200", did)
        state = self._base_state(
            payload_type,
            flush_key,
            self._u200_state.get(did),
            coordinator,
            pending_updates,
        )
        key = spec["key"]
        new_value = coerce_u200_trait_value(spec, value)
        if payload_type != "snapshot":
            self._u200_push_generation += 1
            self._u200_push_versions.setdefault(did, {})[key] = (
                self._u200_push_generation,
                new_value,
            )
        unchanged = key in state and state[key] == new_value
        state[key] = new_value
        self._u200_state[did] = state
        resilient_state = getattr(coordinator, "_aqara_resilient_state", None)
        if isinstance(resilient_state, dict):
            resilient_state["last_data"] = dict(state)
            resilient_state["failures"] = 0
        if unchanged and getattr(coordinator, "last_update_success", True):
            return
        self._queue_state_update(flush_key, coordinator, state, pending_updates)

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
