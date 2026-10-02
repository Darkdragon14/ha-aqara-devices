"""Downloadable, metadata-only diagnostics for experimental Matter locks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return only sanitized capabilities, not entry credentials or runtime state."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    return {"matter_lock_capabilities": deepcopy(data.get("matter_lock_capabilities", []))}
