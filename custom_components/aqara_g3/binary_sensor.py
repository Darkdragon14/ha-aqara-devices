import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import Entity

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USER_ID,
    CONF_REGION,
)
from .aqara_client import pyAqara

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up binary sensors from a config entry."""
    token = entry.data[CONF_TOKEN]
    user_id = entry.data[CONF_USER_ID]
    region = entry.data[CONF_REGION]

    aqara_client = pyAqara(area=region, token=token, userid=user_id)

    coordinator = AqaraFP2DataUpdateCoordinator(hass, aqara_client)
    await coordinator.async_config_entry_first_refresh()

    # Ensure the client session is closed when Home Assistant stops
    entry.async_on_unload(aqara_client.close)

    if not coordinator.data:
        _LOGGER.error("Failed to fetch initial data for Aqara FP2. Entities will not be created.")
        return

    entities = []
    zones = coordinator.data.get("zones", [])
    users = coordinator.data.get("users", [])

    if not zones:
        _LOGGER.warning("No zones found for Aqara FP2. Presence sensors will not be created.")

    # For simplicity, we create a sensor for each zone, assuming presence is zone-based.
    # The original logic created a sensor for each user in each zone.
    # This can be adjusted if per-user presence is desired and the API supports it clearly.
    for zone in zones:
        entities.append(AqaraPresenceBinarySensor(coordinator, zone))

    async_add_entities(entities, update_before_add=True)

class AqaraFP2DataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from Aqara FP2 API."""
    def __init__(self, hass, aqara_client):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.aqara_client = aqara_client

    async def _async_update_data(self):
        """Fetch zones, users and positions from the API."""
        try:
            data = await self.aqara_client.get_position_data()
            if data is None:
                raise UpdateFailed("Failed to fetch data from Aqara API, response was None.")
            
            # Transform data to the format expected by the sensors
            return {
                "zones": data.get("zones", []),
                "users": data.get("users", []),
                "positions": data.get("position", []), # API seems to use "position" key
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

class AqaraPresenceBinarySensor(Entity):
    """Binary sensor for presence detection in a zone."""
    def __init__(self, coordinator, zone):
        self.coordinator = coordinator
        self.zone = zone
        self._attr_name = f"Aqara FP2 Presence - {zone.get('zoneName', 'Unknown Zone')}"
        self._attr_unique_id = f"aqara_fp2_{zone.get('zoneId')}"

    @property
    def is_on(self) -> bool:
        """Return True if any user is present in the zone."""
        if not self.coordinator.data or "positions" not in self.coordinator.data:
            return False
            
        for pos in self.coordinator.data["positions"]:
            if pos.get("zoneId") == self.zone.get("zoneId") and pos.get("presenceState") == 1:
                return True
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.aqara_client._userid)},
            "name": "Aqara FP2 Presence Sensor",
            "manufacturer": "Aqara",
            "model": "FP2",
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_update(self):
        await self.coordinator.async_request_refresh()