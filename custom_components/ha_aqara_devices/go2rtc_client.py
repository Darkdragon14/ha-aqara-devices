from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import BasicAuth, ClientResponseError, ClientSession


class Go2RtcError(Exception):
    """Base go2rtc client error."""


class Go2RtcConnectionError(Go2RtcError):
    """Raised when go2rtc cannot be reached."""


class Go2RtcPairingError(Go2RtcError):
    """Raised when HomeKit pairing fails."""


@dataclass(frozen=True)
class HomeKitCamera:
    """A HomeKit camera discovered by go2rtc."""

    name: str
    url: str


class Go2RtcClient:
    """Small client for the go2rtc APIs used by this integration."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        username: str = "",
        password: str = "",
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._auth = BasicAuth(username, password) if username else None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str]] | dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_response: bool = False,
        allow_not_found: bool = False,
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                data=data,
                auth=self._auth,
                timeout=15,
            ) as response:
                if allow_not_found and response.status == 404:
                    return None
                response.raise_for_status()
                if json_response:
                    return await response.json(content_type=None)
                return await response.read()
        except ClientResponseError as err:
            raise Go2RtcError(f"go2rtc returned HTTP {err.status}") from err
        except Go2RtcError:
            raise
        except Exception as err:
            raise Go2RtcConnectionError("Unable to connect to go2rtc") from err

    async def validate(self) -> dict[str, Any]:
        info = await self._request("GET", "/api", json_response=True)
        schemes = await self._request("GET", "/api/schemes", json_response=True)
        if not isinstance(info, dict) or not isinstance(schemes, list):
            raise Go2RtcError("Invalid go2rtc API response")
        required = {"homekit", "rtsp"}
        if not required.issubset(set(str(item) for item in schemes)):
            raise Go2RtcError("go2rtc does not provide the required HomeKit and RTSP modules")
        return info

    async def discover_homekit(self) -> list[HomeKitCamera]:
        data = await self._request(
            "GET",
            "/api/discovery/homekit",
            json_response=True,
            allow_not_found=True,
        )
        if data is None:
            return []
        items = data.get("sources", data.get("streams", [])) if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        cameras: list[HomeKitCamera] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # go2rtc sets location to its stream ID when it already owns the
            # HomeKit pairing. Those devices belong in the existing-stream flow.
            if str(item.get("location") or "").strip():
                continue
            url = str(item.get("url") or item.get("src") or "").strip()
            if not url:
                continue
            name = str(item.get("name") or item.get("model") or url).strip()
            cameras.append(HomeKitCamera(name=name, url=url))
        return cameras

    async def list_streams(self) -> list[str]:
        data = await self._request("GET", "/api/streams", json_response=True)
        if not isinstance(data, dict):
            raise Go2RtcError("Invalid go2rtc streams response")
        return sorted(str(name) for name in data)

    async def pair_homekit(self, stream_name: str, source: str, pin: str) -> None:
        try:
            await self._request(
                "POST",
                "/api/homekit",
                data={"id": stream_name, "src": source, "pin": pin},
            )
        except Go2RtcError as err:
            raise Go2RtcPairingError(str(err)) from err

    async def unpair_homekit(self, stream_name: str) -> None:
        await self._request("DELETE", "/api/homekit", params={"id": stream_name})

    async def get_snapshot(
        self,
        stream_name: str,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        params = {"src": stream_name}
        if width is not None:
            params["width"] = str(width)
        if height is not None:
            params["height"] = str(height)
        return await self._request("GET", "/api/frame.jpeg", params=params)
