from __future__ import annotations
import base64
import hashlib
import json
import time
import uuid
from typing import Any

from aiohttp import ClientSession
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from .const import AQARA_RSA_PUBKEY, AREAS, REQUEST_PATH, QUERY_PATH

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