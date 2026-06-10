from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from .const import (
    FP2_MODE_LABELS,
    FP2_VIEW_MODES,
    FP2_MOUNTING_POSITIONS,
    FP2_INSTALLATION_ANGLES,
    FP2_SETTING_VALUE_MAPS,
    FP2_ZONE_COUNT,
    FP2_MINUTE_ZONE_COUNT,
)


def _enum_options(value_map: dict) -> list[str]:
    """Build a de-duplicated, order-preserving option list from a value_map."""
    return list(dict.fromkeys(value_map.values()))


def _zone_presence_binary_sensor(index: int) -> dict:
    return {
        "name": f"Detection Area {index}",
        "translation_key": "detection_area",
        "translation_placeholders": {"index": str(index)},
        "key": f"detection_area{index}",
        "api": f"3.{index}.85",
        "poll_group": "fast",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "icon": "mdi:floor-plan",
        "on_values": {"1"},
        "enabled_default": False,
    }


FP2_ZONE_BINARY_SENSORS_DEF = [
    _zone_presence_binary_sensor(index)
    for index in range(1, FP2_ZONE_COUNT + 1)
]

FP2_BINARY_SENSORS_DEF = [
    {
        "key": "fp2_presence_state",
        "api": "3.51.85",
        "poll_group": "presence",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "icon": "mdi:motion-sensor",
        "on_values": {"1"},
    },
    {
        "key": "device_offline_status",
        "api": "8.0.2045",
        "poll_group": "fast",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon": "mdi:lan-connect",
        "on_values": {"1"},
    },
    *FP2_ZONE_BINARY_SENSORS_DEF,
]


def _zone_statistics_sensor(index: int) -> dict:
    return {
        "name": f"Zone {index} People Count (10s)",
        "translation_key": "zone_people_count_10s",
        "translation_placeholders": {"index": str(index)},
        "key": f"zone{index}_statistics",
        "api": f"13.{120 + index}.85",
        "poll_group": "medium",
        "icon": "mdi:counter",
        "value_type": "int",
        "state_class": SensorStateClass.MEASUREMENT,
        "enabled_default": False,
    }


def _zone_minute_statistics_sensor(index: int) -> dict:
    return {
        "name": f"Zone {index} People Count (per minute)",
        "translation_key": "zone_people_count_per_minute",
        "translation_placeholders": {"index": str(index)},
        "key": f"zone{index}_people_counting_by_mins",
        "api": f"0.{120 + index}.85",
        "poll_group": "medium",
        "icon": "mdi:counter",
        "value_type": "float",
        "state_class": SensorStateClass.MEASUREMENT,
        "enabled_default": False,
    }


FP2_COUNT_SENSORS_DEF = [
    {
        "name": "People Counting",
        "translation_key": "people_counting",
        "key": "people_counting",
        "api": "0.60.85",
        "poll_group": "medium",
        "icon": "mdi:account-group",
        "value_type": "float",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "People Counting (per minute)",
        "translation_key": "people_counting_per_minute",
        "key": "people_counting_by_mins",
        "api": "0.61.85",
        "poll_group": "medium",
        "icon": "mdi:counter",
        "value_type": "float",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "name": "Whole Area People Count (10s)",
        "translation_key": "whole_area_people_count_10s",
        "key": "all_zone_statistics",
        "api": "13.120.85",
        "poll_group": "medium",
        "icon": "mdi:home-group",
        "value_type": "int",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    *[
        _zone_statistics_sensor(index)
        for index in range(1, FP2_ZONE_COUNT + 1)
    ],
    *[
        _zone_minute_statistics_sensor(index)
        for index in range(1, FP2_MINUTE_ZONE_COUNT + 1)
    ],
]

FP2_STATUS_SENSORS_DEF = [
    {
        "key": "lux",
        "api": "0.4.85",
        "poll_group": "medium",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "lx",
        "icon": "mdi:brightness-6",
        "value_type": "float",
    },
    {
        "name": "Heart Rate",
        "translation_key": "heart_rate",
        "key": "heartrate_value",
        "api": "0.8.85",
        "poll_group": "medium",
        "unit": "bpm",
        "icon": "mdi:heart-pulse",
        "value_type": "int",
    },
    {
        "name": "Respiration Rate",
        "translation_key": "respiration_rate",
        "key": "respiration_rate_value",
        "api": "0.9.85",
        "poll_group": "medium",
        "unit": "rpm",
        "icon": "mdi:lungs",
        "value_type": "int",
    },
    {
        "name": "Body Movement",
        "translation_key": "body_movement",
        "key": "body_movement_value",
        "api": "13.11.85",
        "poll_group": "fast",
        "icon": "mdi:run",
        "value_type": "int",
    },
    {
        "name": "Sleep State",
        "translation_key": "sleep_state",
        "key": "sleep_state",
        "api": "13.106.85",
        "poll_group": "medium",
        "icon": "mdi:power-sleep",
        "value_type": "str",
    },
    {
        "name": "Operating Mode",
        "translation_key": "operating_mode",
        "key": "set_device_mode4",
        "api": "14.49.85",
        "poll_group": "slow",
        "icon": "mdi:cog",
        "value_type": "str",
        "device_class": SensorDeviceClass.ENUM,
        "value_map": FP2_MODE_LABELS,
        "options": _enum_options(FP2_MODE_LABELS),
    },
    {
        "name": "View Zoom",
        "translation_key": "view_zoom",
        "key": "view_zoom",
        "poll_group": "slow",
        "icon": "mdi:magnify-scan",
        "value_type": "str",
        "device_class": SensorDeviceClass.ENUM,
        "value_map": FP2_VIEW_MODES,
        "options": _enum_options(FP2_VIEW_MODES),
    },
    {
        "name": "Mounting Position",
        "translation_key": "mounting_position",
        "key": "mounting_position",
        "api": "14.57.85",
        "poll_group": "slow",
        "icon": "mdi:wall",
        "value_type": "str",
        "device_class": SensorDeviceClass.ENUM,
        "value_map": FP2_MOUNTING_POSITIONS,
        "options": _enum_options(FP2_MOUNTING_POSITIONS),
    },
    {
        "name": "Installation Angle",
        "translation_key": "installation_angle",
        "key": "installation_angle",
        "api": "13.35.85",
        "poll_group": "slow",
        "icon": "mdi:rotate-3d-variant",
        "value_type": "str",
        "device_class": SensorDeviceClass.ENUM,
        "value_map": FP2_INSTALLATION_ANGLES,
        "options": _enum_options(FP2_INSTALLATION_ANGLES),
    },
    {
        "name": "Attitude Status",
        "translation_key": "attitude_status",
        "key": "attitude_status",
        "api": "13.70.85",
        "poll_group": "slow",
        "icon": "mdi:axis-arrow",
        "value_type": "str",
    },
]


def _fp2_setting_sensor(name: str, translation_key: str, key: str, api: str, icon: str) -> dict:
    value_map = FP2_SETTING_VALUE_MAPS[key]
    return {
        "name": name,
        "translation_key": translation_key,
        "key": key,
        "api": api,
        "poll_group": "slow",
        "icon": icon,
        "value_type": "str",
        "device_class": SensorDeviceClass.ENUM,
        "value_map": value_map,
        "options": _enum_options(value_map),
    }


FP2_SETTINGS_SENSORS_DEF = [
    _fp2_setting_sensor("Presence Sensitivity", "presence_sensitivity", "presence_detection_sens", "14.1.85", "mdi:account-eye"),
    _fp2_setting_sensor("Proximity Distance", "proximity_distance", "proximity_sensing_dist", "14.47.85", "mdi:signal-distance-variant"),
    _fp2_setting_sensor("Fall Detection Sensitivity", "fall_detection_sensitivity", "fall_detection_sens", "14.30.85", "mdi:human-female-fall"),
    _fp2_setting_sensor("Reverse Coordinate Direction", "reverse_coordinate_direction", "reverse_coordinate_dir", "14.51.85", "mdi:axes-arrow"),
    _fp2_setting_sensor("Detection Direction", "detection_direction", "detection_dir", "14.55.85", "mdi:axis-z-arrow"),
    _fp2_setting_sensor("AI Person Detection", "ai_person_detection", "ai_person_det", "4.72.85", "mdi:account-search"),
    _fp2_setting_sensor("Anti-light Pollution Mode", "anti_light_pollution_mode", "anti_light_poll", "4.23.85", "mdi:white-balance-sunny"),
]

FP2_SENSOR_SPECS = [
    *FP2_COUNT_SENSORS_DEF,
    *FP2_STATUS_SENSORS_DEF,
    *FP2_SETTINGS_SENSORS_DEF,
]
