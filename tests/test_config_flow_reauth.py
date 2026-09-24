from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_PATH = ROOT / "custom_components" / "ha_aqara_devices"
PACKAGE = "config_flow_reauth_test_package"
_UNDEFINED = object()


def _module(name: str, **attributes):
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


class _ConfigFlowBase:
    def __init_subclass__(cls, **kwargs):
        return super().__init_subclass__()

    @property
    def source(self):
        return self.context["source"]

    def async_update_reload_and_abort(
        self,
        entry,
        *,
        unique_id=_UNDEFINED,
        title=_UNDEFINED,
        data=_UNDEFINED,
        options=_UNDEFINED,
        reason="reauth_successful",
        reload_even_if_entry_is_unchanged=True,
    ):
        self.hass.config_entries.async_update_entry(entry=entry, data=data)
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason=reason)

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


class _AqaraApi:
    expires_at = 1234.0

    def __init__(self, *args, **kwargs):
        pass

    async def exchange_auth_code(self, auth_code, account):
        return {
            "code": 0,
            "result": {
                "accessToken": "new-access",
                "refreshToken": "new-refresh",
                "openId": "open-id",
            },
        }


def _load_config_flow_module():
    package = ModuleType(PACKAGE)
    package.__path__ = [str(INTEGRATION_PATH)]
    api = _module(f"{PACKAGE}.api", AqaraApi=_AqaraApi)
    sys.modules[PACKAGE] = package
    sys.modules[api.__name__] = api

    config_entries = _module(
        "homeassistant.config_entries",
        ConfigFlow=_ConfigFlowBase,
        SOURCE_REAUTH="reauth",
    )
    selector = _module(
        "homeassistant.helpers.selector",
        TextSelector=lambda config: config,
        TextSelectorConfig=lambda **kwargs: kwargs,
        TextSelectorType=SimpleNamespace(PASSWORD="password"),
    )
    voluptuous = _module(
        "voluptuous",
        All=lambda *args: args,
        In=lambda values: values,
        Length=lambda **kwargs: kwargs,
        Required=lambda value, **kwargs: value,
        Schema=lambda value: value,
    )
    stubs = {
        "voluptuous": voluptuous,
        "homeassistant": _module("homeassistant", config_entries=config_entries),
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": _module("homeassistant.core", callback=lambda func: func),
        "homeassistant.helpers": _module(
            "homeassistant.helpers",
            aiohttp_client=SimpleNamespace(async_get_clientsession=lambda hass: object()),
        ),
        "homeassistant.helpers.selector": selector,
    }
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.config_flow",
        INTEGRATION_PATH / "config_flow.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


config_flow = _load_config_flow_module()


class _ConfigEntries:
    def __init__(self, entry):
        self.entry = entry
        self.updated_data = None
        self.reloaded_entry_id = None

    def async_get_entry(self, entry_id):
        return self.entry if entry_id == self.entry.entry_id else None

    def async_update_entry(self, *, entry, data):
        self.updated_data = data
        return True

    def async_schedule_reload(self, entry_id):
        self.reloaded_entry_id = entry_id


class ConfigFlowReauthTests(unittest.IsolatedAsyncioTestCase):
    async def test_reauth_uses_home_assistant_2024_6_helper_signature(self):
        entry = SimpleNamespace(entry_id="entry-1", data={"preserved": "value"})
        entries = _ConfigEntries(entry)
        flow = config_flow.ConfigFlow()
        flow.hass = SimpleNamespace(config_entries=entries)
        flow.context = {"source": "reauth", "entry_id": entry.entry_id}
        flow._pending_input = {
            "account": "user@example.com",
            "area": "EU",
            "bridge_url": "http://bridge",
            "bridge_token": "bridge-token",
            "app_id": "app-id",
            "app_key": "app-key",
            "key_id": "key-id",
        }

        result = await flow.async_step_auth_code({"auth_code": "123456"})

        self.assertEqual(result, {"type": "abort", "reason": "reauth_successful"})
        self.assertEqual(entries.updated_data["preserved"], "value")
        self.assertEqual(entries.updated_data["access_token"], "new-access")
        self.assertEqual(entries.updated_data["refresh_token"], "new-refresh")
        self.assertEqual(entries.reloaded_entry_id, entry.entry_id)


if __name__ == "__main__":
    unittest.main()
