from __future__ import annotations

import asyncio
from functools import lru_cache
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, Iterable

from aiohttp import ClientSession

from .const import (
    AREAS,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_KEY_ID,
    DEFAULT_ACCESS_TOKEN_VALIDITY,
    FP2_MODEL,
    FP2_RESOURCE_IDS,
    FP2_RESOURCE_KEY_MAP,
    FP300_MODEL,
    G3_MODELS,
    OPEN_API_PATH,
    TOKEN_REFRESH_REQUEST_MARGIN_SECONDS,
)
_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _all_device_defs() -> tuple[dict[str, Any], ...]:
    from .binary_sensors import ALL_BINARY_SENSORS_DEF
    from .numbers import ALL_NUMBERS_DEF
    from .switches import ALL_SWITCHES_DEF

    return tuple(ALL_BINARY_SENSORS_DEF + ALL_SWITCHES_DEF + ALL_NUMBERS_DEF)


@lru_cache(maxsize=1)
def _bridge_runtime() -> dict[str, Any]:
    from .bridge_specs import FP2_GROUP_SPEC_MAPS, FP300_GROUP_SPEC_MAPS, coerce_spec_value, spec_state_key

    fp2_fast = list(FP2_GROUP_SPEC_MAPS["fast"])
    fp2_presence = list(FP2_GROUP_SPEC_MAPS["presence"])
    fp2_medium = list(FP2_GROUP_SPEC_MAPS["medium"])
    fp2_slow = list(FP2_GROUP_SPEC_MAPS["slow"])
    fp300_fast = list(FP300_GROUP_SPEC_MAPS["fast"])
    fp300_medium = list(FP300_GROUP_SPEC_MAPS["medium"])
    fp300_slow = list(FP300_GROUP_SPEC_MAPS["slow"])

    return {
        "FP2_GROUP_SPEC_MAPS": FP2_GROUP_SPEC_MAPS,
        "FP300_GROUP_SPEC_MAPS": FP300_GROUP_SPEC_MAPS,
        "coerce_spec_value": coerce_spec_value,
        "spec_state_key": spec_state_key,
        "FP2_FAST_RESOURCE_IDS": fp2_fast,
        "FP2_PRESENCE_RESOURCE_IDS": fp2_presence,
        "FP2_MEDIUM_RESOURCE_IDS": fp2_medium,
        "FP2_SLOW_RESOURCE_IDS": fp2_slow,
        "FP2_STATUS_RESOURCE_IDS": [*fp2_fast, *fp2_medium, *fp2_slow],
        "FP300_FAST_RESOURCE_IDS": fp300_fast,
        "FP300_MEDIUM_RESOURCE_IDS": fp300_medium,
        "FP300_SLOW_RESOURCE_IDS": fp300_slow,
    }


class AqaraAuthError(RuntimeError):
    """Raised when Aqara credentials are missing, expired, or rejected."""


class AqaraApi:
    """Aqara Open API client."""

    def __init__(
        self,
        area: str,
        session: ClientSession,
        *,
        app_id: str,
        app_key: str,
        key_id: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        open_id: str | None = None,
        expires_at: float | None = None,
    ) -> None:
        area = (area or "OTHER").upper()
        if area not in AREAS:
            area = "OTHER"
        region = AREAS[area]
        if not str(app_id or "").strip() or not str(app_key or "").strip() or not str(key_id or "").strip():
            raise AqaraAuthError(
                f"Aqara developer credentials missing. Configure {CONF_APP_ID}, {CONF_APP_KEY}, and {CONF_KEY_ID}."
            )
        self._area = area
        self._server = region["server"]
        self._appid = str(app_id).strip()
        self._appkey = str(app_key).strip()
        self._keyid = str(key_id).strip()
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._open_id = open_id
        self._expires_at = float(expires_at) if expires_at else None
        self._refresh_lock = asyncio.Lock()

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def refresh_token_value(self) -> str | None:
        return self._refresh_token

    @property
    def open_id(self) -> str | None:
        return self._open_id

    @property
    def expires_at(self) -> float | None:
        return self._expires_at

    def export_auth(self) -> dict[str, Any]:
        return {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "open_id": self._open_id,
            "expires_at": self._expires_at,
        }

    def set_auth(
        self,
        *,
        access_token: str | None,
        refresh_token: str | None,
        open_id: str | None,
        expires_in: str | int | None = None,
        expires_at: float | None = None,
    ) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._open_id = open_id
        if expires_at is not None:
            self._expires_at = float(expires_at)
            return
        if expires_in is None:
            self._expires_at = None
            return
        try:
            self._expires_at = time.time() + int(expires_in)
        except (TypeError, ValueError):
            self._expires_at = None

    def token_expiring_soon(self, margin_seconds: int = TOKEN_REFRESH_REQUEST_MARGIN_SECONDS) -> bool:
        if not self._access_token:
            return True
        if self._expires_at is None:
            return False
        return time.time() >= (self._expires_at - margin_seconds)

    def _sign(self, headers: dict[str, str]) -> str:
        sign_parts: list[str] = []
        access_token = headers.get("Accesstoken")
        if access_token:
            sign_parts.append(f"Accesstoken={access_token}")
        sign_parts.extend(
            [
                f"Appid={headers['Appid']}",
                f"Keyid={headers['Keyid']}",
                f"Nonce={headers['Nonce']}",
                f"Time={headers['Time']}",
            ]
        )
        source = "&".join(sign_parts) + self._appkey
        return hashlib.md5(source.lower().encode()).hexdigest()

    @staticmethod
    def _redact_data(value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {
                    "accesstoken",
                    "access_token",
                    "refreshtoken",
                    "refresh_token",
                    "authcode",
                    "auth_code",
                    "sign",
                    "appkey",
                }:
                    redacted[key] = "<redacted>"
                else:
                    redacted[key] = AqaraApi._redact_data(item)
            return redacted
        if isinstance(value, list):
            return [AqaraApi._redact_data(item) for item in value]
        return value

    @staticmethod
    def _summarize_response(data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        result = data.get("result")
        if isinstance(result, list):
            result_summary: Any = {"items": len(result)}
        elif isinstance(result, dict):
            result_summary = {"keys": sorted(result.keys())}
            if isinstance(result.get("data"), list):
                result_summary["data_items"] = len(result["data"])
        else:
            result_summary = result
        return {
            "code": data.get("code"),
            "message": data.get("message"),
            "msgDetails": data.get("msgDetails"),
            "requestId": data.get("requestId"),
            "result": result_summary,
        }

    def _open_headers(self, access_token: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {
            "Appid": self._appid,
            "Keyid": self._keyid,
            "Nonce": uuid.uuid4().hex,
            "Time": str(int(time.time() * 1000)),
            "Lang": "en",
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Accesstoken"] = access_token
        headers["Sign"] = self._sign(headers)
        return headers

    async def _decode_response(self, resp) -> Any:
        text = await resp.text()
        if not text:
            return {"code": resp.status, "message": "Empty response", "result": ""}
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise RuntimeError(f"Aqara returned non-JSON response: {text[:200]}") from err

    @staticmethod
    def _is_auth_error(data: Any) -> bool:
        if not isinstance(data, dict):
            return False
        code = str(data.get("code", ""))
        if code in {"401", "403", "1005", "1006", "1008", "1013"}:
            return True
        message = str(data.get("message") or "").lower()
        details = str(data.get("msgDetails") or "").lower()
        auth_markers = ("token", "auth", "unauthorized", "expired")
        return any(marker in message or marker in details for marker in auth_markers)

    async def ensure_valid_access_token(self, margin_seconds: int = TOKEN_REFRESH_REQUEST_MARGIN_SECONDS) -> None:
        if self.token_expiring_soon(margin_seconds):
            await self.refresh_access_token()

    async def _open_request(
        self,
        intent: str,
        data: Any,
        *,
        authenticated: bool,
        retry_on_auth: bool = True,
    ) -> Any:
        access_token = None
        if authenticated:
            await self.ensure_valid_access_token()
            if not self._access_token:
                raise AqaraAuthError("Aqara access token missing")
            access_token = self._access_token

        body = json.dumps({"intent": intent, "data": data}, separators=(",", ":"))
        url = f"{self._server}{OPEN_API_PATH}"
        _LOGGER.debug(
            "Aqara Open API request: intent=%s authenticated=%s area=%s payload=%s",
            intent,
            authenticated,
            self._area,
            self._redact_data(data),
        )
        async with self._session.post(url, data=body, headers=self._open_headers(access_token)) as resp:
            response_data = await self._decode_response(resp)
        _LOGGER.debug(
            "Aqara Open API response: intent=%s status=%s summary=%s",
            intent,
            getattr(resp, "status", "unknown"),
            self._summarize_response(response_data),
        )

        if authenticated and retry_on_auth and self._is_auth_error(response_data):
            _LOGGER.debug("Aqara Open API auth retry triggered for intent=%s", intent)
            await self.refresh_access_token(force=True)
            return await self._open_request(intent, data, authenticated=True, retry_on_auth=False)

        if authenticated and self._is_auth_error(response_data):
            raise AqaraAuthError(f"Aqara authentication failed for {intent}: {self._summarize_response(response_data)}")

        return response_data

    async def request_auth_code(
        self,
        account: str,
        account_type: int = 0,
        access_token_validity: str = DEFAULT_ACCESS_TOKEN_VALIDITY,
    ) -> Any:
        return await self._open_request(
            "config.auth.getAuthCode",
            {
                "account": account,
                "accountType": account_type,
                "accessTokenValidity": access_token_validity,
            },
            authenticated=False,
        )

    async def exchange_auth_code(self, auth_code: str, account: str, account_type: int = 0) -> Any:
        data = await self._open_request(
            "config.auth.getToken",
            {
                "authCode": auth_code,
                "account": account,
                "accountType": account_type,
            },
            authenticated=False,
        )
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Aqara token exchange failed: {data}")
        result = data.get("result") or {}
        self.set_auth(
            access_token=result.get("accessToken"),
            refresh_token=result.get("refreshToken"),
            open_id=result.get("openId"),
            expires_in=result.get("expiresIn"),
        )
        return data

    async def refresh_access_token(self, force: bool = False) -> Any:
        async with self._refresh_lock:
            if not force and not self.token_expiring_soon():
                return {"code": 0, "result": self.export_auth()}
            if not self._refresh_token:
                raise AqaraAuthError("Aqara refresh token missing")
            data = await self._open_request(
                "config.auth.refreshToken",
                {"refreshToken": self._refresh_token},
                authenticated=False,
                retry_on_auth=False,
            )
            if str(data.get("code")) != "0":
                if self._is_auth_error(data):
                    raise AqaraAuthError(f"Aqara refresh token failed: {self._summarize_response(data)}")
                raise RuntimeError(f"Aqara refresh token failed: {data}")
            result = data.get("result") or {}
            self.set_auth(
                access_token=result.get("accessToken"),
                refresh_token=result.get("refreshToken"),
                open_id=result.get("openId"),
                expires_in=result.get("expiresIn"),
            )
            return data

    async def res_write(self, payload: dict) -> Any:
        subject_id = payload["subjectId"]
        data = [
            {
                "subjectId": subject_id,
                "resources": [
                    {"resourceId": resource_id, "value": str(value)}
                    for resource_id, value in (payload.get("data") or {}).items()
                ],
            }
        ]
        return await self._open_request("write.resource.device", data, authenticated=True)

    async def res_query(self, payload: dict) -> Any:
        resources = []
        for item in payload.get("data") or []:
            resources.append(
                {
                    "subjectId": item["subjectId"],
                    "resourceIds": item.get("options") or item.get("resourceIds") or [],
                }
            )
        response = await self._open_request("query.resource.value", {"resources": resources}, authenticated=True)
        if (
            str(response.get("code")) == "302"
            and str(response.get("msgDetails") or "").lower() == "all resource not open"
        ):
            fallback = await self._query_resources_individually(resources)
            if fallback is not None:
                return fallback
        return response

    async def _query_resources_individually(self, resources: list[dict[str, Any]]) -> Any | None:
        merged_items: list[dict[str, Any]] = []
        skipped: list[str] = []

        for resource in resources:
            subject_id = resource["subjectId"]
            for resource_id in resource.get("resourceIds") or []:
                single_response = await self._open_request(
                    "query.resource.value",
                    {"resources": [{"subjectId": subject_id, "resourceIds": [resource_id]}]},
                    authenticated=True,
                )
                if str(single_response.get("code")) == "0":
                    merged_items.extend(self._flatten_result_items(single_response))
                else:
                    skipped.append(str(resource_id))

        if not merged_items:
            if skipped:
                _LOGGER.debug("Aqara individual resource fallback skipped all resources: %s", skipped)
            return {
                "code": 0,
                "message": "Success",
                "msgDetails": "No open resources returned",
                "requestId": "fallback-individual-query",
                "result": [],
            }

        if skipped:
            _LOGGER.debug("Aqara individual resource fallback skipped resources: %s", skipped)

        return {
            "code": 0,
            "message": "Success",
            "msgDetails": None if not skipped else f"Skipped unopened resources: {', '.join(skipped)}",
            "requestId": "fallback-individual-query",
            "result": merged_items,
        }

    async def res_history(self, payload: dict) -> Any:
        data = {
            "subjectId": payload["subjectId"],
            "resourceIds": payload.get("resourceIds") or [],
            "startTime": payload.get("startTime", 1514736000000),
            "endTime": payload.get("endTime", int(time.time() * 1000)),
            "size": payload.get("size", 30),
            "scanId": payload.get("scanId", ""),
        }
        return await self._open_request("fetch.resource.history", data, authenticated=True)

    async def res_query_resource(self, payload: dict) -> Any:
        data_items = payload.get("data") or []
        translated = {
            "data": [
                {
                    "subjectId": item["subjectId"],
                    "options": item.get("options") or item.get("resourceIds") or [],
                }
                for item in data_items
            ]
        }
        return await self.res_query(translated)

    async def subscribe_resources(self, subscriptions: list[dict[str, Any]]) -> Any:
        data = {"resources": subscriptions}
        return await self._open_request("config.resource.subscribe", data, authenticated=True)

    async def unsubscribe_resources(self, subscriptions: list[dict[str, Any]]) -> Any:
        data = {"resources": subscriptions}
        return await self._open_request("config.resource.unsubscribe", data, authenticated=True)

    @staticmethod
    def _flatten_result_items(data: Any) -> list[dict]:
        raw_result = data.get("result", []) if isinstance(data, dict) else []
        if isinstance(raw_result, list):
            return [item for item in raw_result if isinstance(item, dict)]
        if isinstance(raw_result, dict):
            for key in ("attributes", "data", "list", "items", "result"):
                maybe = raw_result.get(key)
                if isinstance(maybe, list):
                    return [item for item in maybe if isinstance(item, dict)]
        return []

    @staticmethod
    def _attr_value_from_item(item: dict) -> Any:
        value = item.get("value")
        if isinstance(value, dict) and "value" in value:
            return value.get("value")
        return value

    async def get_device_states(
        self,
        did: str,
        switch_defs: Iterable[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        if switch_defs is None:
            switch_defs = _all_device_defs()
        standard_defs = [spec for spec in switch_defs if spec.get("api")]
        history_defs = [spec for spec in switch_defs if spec.get("history_resource")]
        result_map: Dict[str, Any] = {spec["inApp"]: spec.get("default", 0) for spec in switch_defs}

        if standard_defs:
            api_to_spec = {spec["api"]: spec for spec in standard_defs}
            payload = {
                "data": [
                    {
                        "options": list(api_to_spec.keys()),
                        "subjectId": did,
                    }
                ]
            }
            data = await self.res_query(payload)
            if str(data.get("code")) != "0":
                raise RuntimeError(f"Failed to query device states: {data}")
            _LOGGER.debug(
                "Aqara device states fetched: did=%s requested=%s returned=%s",
                did,
                list(api_to_spec.keys()),
                [str(item.get("resourceId") or item.get("attr") or "") for item in self._flatten_result_items(data)],
            )

            for item in self._flatten_result_items(data):
                key = str(item.get("resourceId") or item.get("attr") or "")
                val = self._attr_value_from_item(item)
                spec = api_to_spec.get(key)
                if spec:
                    result_map[spec["inApp"]] = _bridge_runtime()["coerce_spec_value"](spec, val, apply_scale=True)

        if history_defs:
            result_map.update(await self._history_states(did, history_defs))

        return result_map

    async def _history_states(self, did: str, specs: Iterable[Dict[str, Any]]) -> Dict[str, float]:
        spec_list = list(specs)
        history_map: Dict[str, float] = {}
        resource_ids = list({spec["history_resource"] for spec in spec_list})
        max_size = max((spec.get("history_size", 10) for spec in spec_list), default=10)
        payload = {
            "resourceIds": resource_ids,
            "scanId": "",
            "size": max_size,
            "startTime": 1514736000000,
            "subjectId": did,
        }

        data = await self.res_history(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query device history: {data}")
        _LOGGER.debug(
            "Aqara history fetched: did=%s resources=%s items=%s",
            did,
            resource_ids,
            len(self._flatten_result_items(data)),
        )

        grouped: Dict[str, list[dict]] = {}
        for event in self._flatten_result_items(data):
            rid = str(event.get("resourceId") or event.get("attr") or "")
            if not rid:
                continue
            grouped.setdefault(rid, []).append(event)

        for spec in spec_list:
            rid = spec["history_resource"]
            desired = str(spec.get("history_value"))
            for event in grouped.get(rid, []):
                value = str(event.get("value"))
                if value != desired:
                    continue
                ts: Any = event.get("timeStamp") or event.get("timestamp") or event.get("time")
                try:
                    ts_val = float(ts)
                except (TypeError, ValueError):
                    _LOGGER.debug("Could not parse timestamp for %s: %s", spec["inApp"], event)
                    break
                if ts_val > 1_000_000_000_000:
                    ts_val = ts_val / 1000.0
                history_map[spec["inApp"]] = ts_val
                break

        return history_map

    async def get_devices(self) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        page_num = 1
        page_size = 50

        while True:
            data = await self._open_request(
                "query.device.info",
                {
                    "positionId": "",
                    "pageNum": page_num,
                    "pageSize": page_size,
                },
                authenticated=True,
            )
            if str(data.get("code")) != "0":
                raise RuntimeError(f"Failed to fetch devices: {data}")
            result = data.get("result") or {}
            page_devices = result.get("data") or []
            if not isinstance(page_devices, list):
                page_devices = []
            _LOGGER.debug(
                "Aqara devices page fetched: page=%s page_size=%s items=%s total=%s",
                page_num,
                page_size,
                len(page_devices),
                result.get("totalCount"),
            )
            devices.extend(device for device in page_devices if isinstance(device, dict))
            total_count = int(result.get("totalCount") or len(devices) or 0)
            if len(devices) >= total_count or not page_devices:
                break
            page_num += 1

        return devices

    async def get_devices_by_model(self, model: str) -> list[dict[str, Any]]:
        devices = await self.get_devices()
        return [d for d in devices if d.get("model") == model]

    async def get_cameras(self) -> list[dict[str, Any]]:
        devices = await self.get_devices()
        return [d for d in devices if d.get("model") in G3_MODELS]

    async def get_fp2_devices(self) -> list[dict[str, Any]]:
        return await self.get_devices_by_model(FP2_MODEL)

    async def _query_presence_status_attrs(
        self,
        did: str,
        attrs: Iterable[str],
        resource_specs: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        options = list(dict.fromkeys(attrs))
        if not options:
            return {}
        payload = {"data": [{"options": options, "subjectId": did}]}
        data = await self.res_query(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query presence status: {data}")
        _LOGGER.debug(
            "Aqara presence status fetched: did=%s requested=%s returned=%s",
            did,
            options,
            [str(item.get("resourceId") or item.get("attr") or "") for item in self._flatten_result_items(data)],
        )
        if resource_specs:
            return self._map_resource_status(data, resource_specs, apply_scale=False)
        status: dict[str, Any] = {}
        for item in self._flatten_result_items(data):
            attr = str(item.get("resourceId") or item.get("attr") or "")
            if not attr:
                continue
            status[attr] = self._attr_value_from_item(item)
        return status

    @staticmethod
    def _merge_states(*parts: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for part in parts:
            merged.update(part)
        return merged

    def _map_resource_status(
        self,
        data: Any,
        resource_specs: dict[str, dict[str, Any]],
        *,
        apply_scale: bool,
    ) -> dict[str, Any]:
        runtime = _bridge_runtime()
        status: dict[str, Any] = {}
        for item in self._flatten_result_items(data):
            resource_id = str(item.get("resourceId") or item.get("attr") or "")
            spec = resource_specs.get(resource_id)
            if not spec:
                continue
            key = runtime["spec_state_key"](spec)
            if not key:
                continue
            status[key] = runtime["coerce_spec_value"](spec, self._attr_value_from_item(item), apply_scale=apply_scale)
        return status

    async def get_presence_core_state(self, did: str, model: str) -> dict[str, Any]:
        runtime = _bridge_runtime()
        if model == FP2_MODEL:
            return await self.get_fp2_full_state(did)
        if model == FP300_MODEL:
            return await self._query_presence_status_attrs(
                did,
                [
                    *runtime["FP300_FAST_RESOURCE_IDS"],
                    *runtime["FP300_MEDIUM_RESOURCE_IDS"],
                    *runtime["FP300_SLOW_RESOURCE_IDS"],
                ],
                {
                    **runtime["FP300_GROUP_SPEC_MAPS"]["fast"],
                    **runtime["FP300_GROUP_SPEC_MAPS"]["medium"],
                    **runtime["FP300_GROUP_SPEC_MAPS"]["slow"],
                },
            )
        raise RuntimeError(f"Unsupported presence model: {model}")

    async def get_presence_fast_state(self, did: str, model: str) -> dict[str, Any]:
        runtime = _bridge_runtime()
        if model == FP2_MODEL:
            return await self.get_fp2_status(did, runtime["FP2_FAST_RESOURCE_IDS"])
        if model == FP300_MODEL:
            return await self._query_presence_status_attrs(
                did,
                runtime["FP300_FAST_RESOURCE_IDS"],
                runtime["FP300_GROUP_SPEC_MAPS"]["fast"],
            )
        raise RuntimeError(f"Unsupported presence model: {model}")

    async def get_presence_medium_state(self, did: str, model: str) -> dict[str, Any]:
        runtime = _bridge_runtime()
        if model == FP2_MODEL:
            return await self.get_fp2_status(did, runtime["FP2_MEDIUM_RESOURCE_IDS"])
        if model == FP300_MODEL:
            return await self._query_presence_status_attrs(
                did,
                runtime["FP300_MEDIUM_RESOURCE_IDS"],
                runtime["FP300_GROUP_SPEC_MAPS"]["medium"],
            )
        raise RuntimeError(f"Unsupported presence model: {model}")

    async def get_presence_slow_state(self, did: str, model: str) -> dict[str, Any]:
        runtime = _bridge_runtime()
        if model == FP2_MODEL:
            status, settings = await asyncio.gather(
                self.get_fp2_status(did, runtime["FP2_SLOW_RESOURCE_IDS"]),
                self.get_fp2_settings(did),
            )
            return self._merge_states(status, settings)
        if model == FP300_MODEL:
            return await self._query_presence_status_attrs(
                did,
                runtime["FP300_SLOW_RESOURCE_IDS"],
                runtime["FP300_GROUP_SPEC_MAPS"]["slow"],
            )
        raise RuntimeError(f"Unsupported presence model: {model}")

    async def get_fp2_status(self, did: str, attrs: Iterable[str] | None = None) -> dict[str, Any]:
        runtime = _bridge_runtime()
        options = list(dict.fromkeys(attrs or runtime["FP2_STATUS_RESOURCE_IDS"]))
        resource_specs = {
            **runtime["FP2_GROUP_SPEC_MAPS"]["fast"],
            **runtime["FP2_GROUP_SPEC_MAPS"]["medium"],
            **runtime["FP2_GROUP_SPEC_MAPS"]["slow"],
        }
        return await self._query_presence_status_attrs(did, options, resource_specs)

    async def get_fp2_settings(self, did: str) -> dict[str, Any]:
        payload = {"data": [{"options": FP2_RESOURCE_IDS, "subjectId": did}]}
        data = await self.res_query_resource(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query FP2 settings: {data}")
        _LOGGER.debug(
            "Aqara FP2 settings fetched: did=%s resources=%s returned=%s",
            did,
            FP2_RESOURCE_IDS,
            [str(item.get("resourceId") or item.get("attr") or "") for item in self._flatten_result_items(data)],
        )
        settings: dict[str, Any] = {}
        for item in self._flatten_result_items(data):
            rid = str(item.get("resourceId") or item.get("attr") or "")
            key = FP2_RESOURCE_KEY_MAP.get(rid)
            if not key:
                continue
            settings[key] = self._attr_value_from_item(item)
        return settings

    async def get_fp2_presence(self, did: str) -> dict[str, Any]:
        runtime = _bridge_runtime()
        return await self._query_presence_status_attrs(
            did,
            runtime["FP2_PRESENCE_RESOURCE_IDS"],
            runtime["FP2_GROUP_SPEC_MAPS"]["presence"],
        )

    async def get_fp2_full_state(self, did: str) -> dict[str, Any]:
        status, settings, presence = await asyncio.gather(
            self.get_fp2_status(did),
            self.get_fp2_settings(did),
            self.get_fp2_presence(did),
        )
        return self._merge_states(status, settings, presence)

    async def camera_operate(self, did: str, action: str) -> Dict[str, Any]:
        raise NotImplementedError(
            f"Open API camera operate is not implemented yet for {did} ({action})"
        )
