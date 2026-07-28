from __future__ import annotations

from typing import Any

from homeassistant.helpers import entity_registry as er

from .const import G410_ACN017_MODEL


G410_AGL006_OBSOLETE_ENTITY_KEYS = {
    "detect_stranger_face_event",
    "time_sleep_enable",
    "device_night_tip_light",
    "doorbell_push_enable",
    "doorbell_record_enable",
    "image_flip",
    "restart_device",
    "restart_coordinator",
}


def remove_obsolete_g410_entities(
    hass,
    entry_id: str,
    g410_doorbells: list[dict[str, Any]],
) -> None:
    obsolete_unique_ids = {
        f"{doorbell['did']}_{entity_key}"
        for doorbell in g410_doorbells
        if doorbell.get("model") != G410_ACN017_MODEL
        for entity_key in G410_AGL006_OBSOLETE_ENTITY_KEYS
    }
    if not obsolete_unique_ids:
        return

    entity_registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        if registry_entry.unique_id in obsolete_unique_ids:
            entity_registry.async_remove(registry_entry.entity_id)
