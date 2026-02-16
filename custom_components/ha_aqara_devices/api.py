from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import logging
import time
import uuid
from typing import Dict, Any, Iterable

from aiohttp import ClientSession
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from .const import (
    AQARA_RSA_PUBKEY,
    AREAS,
    REQUEST_PATH,
    QUERY_PATH,
    HISTORY_PATH,
    DEVICES_PATH,
    OPERATE_PATH,
    RESOURCE_QUERY_PATH,
    G3_MODEL,
    FP2_MODEL,
    FP2_STATUS_ATTRS,
    FP2_RESOURCE_IDS,
    FP2_RESOURCE_KEY_MAP,
    FP2_PRESENCE_RESOURCES,
)
from .switches import ALL_SWITCHES_DEF
from .binary_sensors import ALL_BINARY_SENSORS_DEF
from .numbers import ALL_NUMBERS_DEF

ALL_DEF = ALL_BINARY_SENSORS_DEF + ALL_SWITCHES_DEF + ALL_NUMBERS_DEF
_LOGGER = logging.getLogger(__name__)

class AqaraApi:
    """Tiny Aqara mobile API client for this MVP."""

    def __init__(self, area: str, session: ClientSession) -> None:
        area = (area or "OTHER").upper()
        if area not in AREAS:
            area = "OTHER"
        self._area = area
        self._server = AREAS[area]["server"]
        self._appid = AREAS[area]["appid"]
        self._appkey = AREAS[area]["appkey"]
        self._token: str | None = None
        self._userid: str | None = None
        self._session = session
        self._base_headers = {
            "User-Agent": "pyAqara/1.0.0",
            "App-Version": "3.0.0",
            "Sys-Type": "1",
            "Lang": "en",
            "Phone-Model": "pyAqara",
            "PhoneId": str(uuid.uuid4()).upper(),
        }

    @staticmethod
    def _rsa_encrypt_md5(password: str) -> str:
        md5hex = hashlib.md5(password.encode()).hexdigest().encode()
        cipher = PKCS1_v1_5.new(RSA.import_key(AQARA_RSA_PUBKEY))
        enc = cipher.encrypt(md5hex)
        return base64.b64encode(enc).decode()

    def _sign(self, headers: dict) -> str:
        # Order as the token generator script
        if headers.get("Token"):
            s = (
                f"Appid={headers['Appid']}&Nonce={headers['Nonce']}"
                f"&Time={headers['Time']}&Token={headers['Token']}"
                f"&{headers['RequestBody']}&&{headers['Appkey']}".replace("&&","&")
            )
        else:
            s = (
                f"Appid={headers['Appid']}&Nonce={headers['Nonce']}"
                f"&Time={headers['Time']}&{headers['RequestBody']}&{headers['Appkey']}"
            )
        return hashlib.md5(s.encode()).hexdigest()

    def _auth_headers(self, request_body: str) -> dict:
        h = {
            **self._base_headers,
            "Area": self._area,  # required for login per script
            "Appid": self._appid,
            "Appkey": self._appkey,
            "Nonce": hashlib.md5(str(uuid.uuid4()).encode()).hexdigest(),
            "Time": str(int(time.time() * 1000)),
            "RequestBody": request_body,
        }
        if self._token:
            h["Token"] = self._token
        h["Sign"] = self._sign(h)
        # Remove helper fields not to be sent
        del h["Appkey"]
        del h["RequestBody"]
        h["Content-Type"] = "application/json"
        return h

    async def login(self, username: str, password: str) -> str:
        body = json.dumps({
            "account": username,
            "encryptType": 2,
            "password": self._rsa_encrypt_md5(password),
        })
        url = f"{self._server}/app/v1.0/lumi/user/login"
        async with self._session.post(url, data=body, headers=self._auth_headers(body)) as resp:
            data = await resp.json(content_type=None)
        if data.get("code") != 0:
            raise RuntimeError(f"Aqara login failed: {data}")
        res = data["result"]
        self._token = res["token"]
        self._userid = res.get("userId") or res.get("userid")
        return self._token

    def _rest_headers(self) -> dict:
        """Headers for res/write and res/query (token-based, no Sign)."""
        if not self._token or not self._userid:
            raise RuntimeError("Not logged in: token/userid missing")
        return {
            "Sys-Type": "1",
            "Appid": self._appid,
            "Userid": self._userid,
            "Token": self._token,
            "Content-Type": "application/json; charset=utf-8",
        }

    async def res_write(self, payload: dict) -> Any:
        url = f"{self._server}{REQUEST_PATH}"
        body = json.dumps(payload)
        async with self._session.post(url, data=body, headers=self._rest_headers()) as resp:
            return await resp.json(content_type=None)

    async def res_query(self, payload: dict) -> Any:
        url = f"{self._server}{QUERY_PATH}"
        body = json.dumps(payload)
        async with self._session.post(url, data=body, headers=self._rest_headers()) as resp:
            return await resp.json(content_type=None)

    async def res_history(self, payload: dict) -> Any:
        url = f"{self._server}{HISTORY_PATH}"
        body = json.dumps(payload)
        async with self._session.post(url, data=body, headers=self._rest_headers()) as resp:
            return await resp.json(content_type=None)

    async def res_query_resource(self, payload: dict) -> Any:
        url = f"{self._server}{RESOURCE_QUERY_PATH}"
        body = json.dumps(payload)
        async with self._session.post(url, data=body, headers=self._rest_headers()) as resp:
            return await resp.json(content_type=None)

    @staticmethod
    def _flatten_result_items(data: Any) -> list[dict]:
        raw_result = data.get("result", [])
        if isinstance(raw_result, list):
            return raw_result
        if isinstance(raw_result, dict):
            for key in ("attributes", "data", "list", "items", "result"):
                maybe = raw_result.get(key)
                if isinstance(maybe, list):
                    return maybe
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
        switch_defs: Iterable[Dict[str, Any]] = ALL_DEF,
    ) -> Dict[str, Any]:
        """
        Query multiple boolean-like attributes in one call, based on switch defs.
        Returns a dict { <inApp>: 0|1, ... } for all provided switch_defs.
        """

        # Separate standard attributes from history-derived ones
        standard_defs = [spec for spec in switch_defs if spec.get("api")]
        history_defs = [spec for spec in switch_defs if spec.get("history_resource")]

        # Initialize result with 0 for every inApp (so missing attrs default to 0)
        result_map: Dict[str, Any] = {spec["inApp"]: spec.get("default", 0) for spec in switch_defs}

        if standard_defs:
            # Map api -> spec for fast reverse lookup
            api_to_spec = {spec["api"]: spec for spec in standard_defs}

            # Build options list from all APIs
            options = list(api_to_spec.keys())

            payload = {
                "data": [{
                    "options": options,
                    "subjectId": did,
                }]
            }

            data = await self.res_query(payload)
            if str(data.get("code")) != "0":
                raise RuntimeError(f"Failed to query device states: {data}")

            def _to01(v) -> int:
                try:
                    return 1 if int(v) == 1 else 0
                except Exception:
                    return 1 if str(v).strip().lower() in ("1", "on", "true", "yes") else 0

            def _coerce_value(spec: Dict[str, Any], val: Any) -> Any:
                if val is None:
                    return spec.get("default", 0)
                value_type = spec.get("value_type") or spec.get("type")
                if value_type in ("int", "integer", "uint8_t", "uint16_t", "uint32_t"):
                    try:
                        parsed: Any = int(float(val))
                    except Exception:
                        parsed = 0
                elif value_type == "float":
                    try:
                        parsed = float(val)
                    except Exception:
                        parsed = 0.0
                elif value_type == "string":
                    parsed = "" if val is None else str(val)
                elif value_type == "bool":
                    parsed = _to01(val)
                else:
                    parsed = _to01(val)
                scale = spec.get("scale")
                if scale is not None:
                    try:
                        parsed = float(parsed) * float(scale)
                    except Exception:
                        pass
                return parsed

            items = self._flatten_result_items(data)
            for item in items:
                key = item.get("attr")
                val = self._attr_value_from_item(item)
                spec = api_to_spec.get(key)
                if spec:
                    in_app = spec["inApp"]
                    result_map[in_app] = _coerce_value(spec, val)

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

        raw_result = data.get("result") or {}
        events = []
        if isinstance(raw_result, list):
            events = raw_result
        elif isinstance(raw_result, dict):
            for key in ("data", "list", "items"):
                maybe = raw_result.get(key)
                if isinstance(maybe, list):
                    events = maybe
                    break

        grouped: Dict[str, list[dict]] = {}
        for event in events or []:
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
                ts = event.get("timeStamp") or event.get("timestamp") or event.get("time")
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
        """Fetch all devices from Aqara cloud."""
        url = f"{self._server}{DEVICES_PATH}"
        headers = {
            "Sys-type": "1",
            "AppId": "444c476ef7135e53330f46e7",
            "UserId": self._userid,
            "Token": self._token,
            "Content-Type": "application/json; charset=utf-8",
        }

        async with self._session.get(url, headers=self._rest_headers(), json={}) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch devices: {resp.status}")
            body = await resp.json()

        return body.get("result", {}).get("devices", [])

    async def get_devices_by_model(self, model: str) -> list[dict[str, Any]]:
        devices = await self.get_devices()
        return [d for d in devices if d.get("model") == model]

    async def get_cameras(self) -> list[dict[str, Any]]:
        """Filter only Aqara G3 cameras."""
        return await self.get_devices_by_model(G3_MODEL)

    async def get_fp2_devices(self) -> list[dict[str, Any]]:
        """Filter Aqara FP2 presence sensors."""
        return await self.get_devices_by_model(FP2_MODEL)

    async def get_fp2_status(self, did: str) -> dict[str, Any]:
        payload = {
            "data": [{
                "options": FP2_STATUS_ATTRS,
                "subjectId": did,
            }]
        }
        data = await self.res_query(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query FP2 status: {data}")
        status: dict[str, Any] = {}
        for item in self._flatten_result_items(data):
            attr = item.get("attr")
            if not attr:
                continue
            status[attr] = self._attr_value_from_item(item)
        return status

    async def get_fp2_settings(self, did: str) -> dict[str, Any]:
        payload = {
            "data": [{
                "options": FP2_RESOURCE_IDS,
                "subjectId": did,
            }]
        }
        data = await self.res_query_resource(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query FP2 settings: {data}")
        settings: dict[str, Any] = {}
        for item in self._flatten_result_items(data):
            rid = str(item.get("resourceId") or item.get("attr") or "")
            key = FP2_RESOURCE_KEY_MAP.get(rid)
            if not key:
                continue
            settings[key] = self._attr_value_from_item(item)
        return settings

    async def get_fp2_presence(self, did: str) -> dict[str, Any]:
        if not FP2_PRESENCE_RESOURCES:
            return {}
        payload = {
            "resourceIds": FP2_PRESENCE_RESOURCES,
            "scanId": "",
            "size": 5,
            "startTime": 1514736000000,
            "subjectId": did,
        }
        data = await self.res_history(payload)
        if str(data.get("code")) != "0":
            raise RuntimeError(f"Failed to query FP2 presence history: {data}")
        best_ts = -1.0
        best_val: Any = None
        best_rid: str | None = None
        raw_result = data.get("result") or {}
        events = []
        if isinstance(raw_result, list):
            events = raw_result
        elif isinstance(raw_result, dict):
            for key in ("data", "list", "items"):
                maybe = raw_result.get(key)
                if isinstance(maybe, list):
                    events = maybe
                    break
        for event in events or []:
            rid = str(event.get("resourceId") or event.get("attr") or "")
            if rid not in FP2_PRESENCE_RESOURCES:
                continue
            ts = event.get("timeStamp") or event.get("timestamp") or event.get("time")
            try:
                ts_val = float(ts)
            except (TypeError, ValueError):
                continue
            if ts_val > 1_000_000_000_000:
                ts_val = ts_val / 1000.0
            if ts_val > best_ts:
                best_ts = ts_val
                best_val = event.get("value")
                best_rid = rid
        if best_val is None:
            return {}
        presence = 1 if str(best_val) == "1" else 0
        return {
            "fp2_presence_state": presence,
            "fp2_presence_ts": best_ts,
            "fp2_presence_source": best_rid,
        }

    async def get_fp2_full_state(self, did: str) -> dict[str, Any]:
        status, settings, presence = await asyncio.gather(
            self.get_fp2_status(did),
            self.get_fp2_settings(did),
            self.get_fp2_presence(did),
        )
        merged = {}
        merged.update(status)
        merged.update(settings)
        merged.update(presence)
        return merged

    async def camera_operate(self, did: str, action: str) -> Dict[str, Any]:
        payload = {
            "method": "ctrl_ptz",
            "params": {"action": action},
            "did": did,
        }
        url = f"{self._server}{OPERATE_PATH}"
        body = json.dumps(payload)
        async with self._session.post(url, data=body, headers=self._rest_headers()) as resp:
            if resp.status != 200:
                raise Exception(f"Failed to fetch devices: {resp.status}")
            return True
