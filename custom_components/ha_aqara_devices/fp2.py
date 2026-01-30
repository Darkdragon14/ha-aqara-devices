from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass

from .const import (
    FP2_MODE_LABELS,
    FP2_VIEW_MODES,
    FP2_MOUNTING_POSITIONS,
    FP2_INSTALLATION_ANGLES,
    FP2_SETTING_VALUE_MAPS,
)

FP2_BINARY_SENSORS_DEF = [
    {
        "name": "Presence",
        "key": "fp2_presence_state",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "icon": "mdi:motion-sensor",
        "on_values": {"1"},
    },
    {
        "name": "Connectivity",
        "key": "device_offline_status",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon": "mdi:lan-connect",
        "on_values": {"0"},
    },
]

FP2_STATUS_SENSORS_DEF = [
    {
        "name": "Illuminance",
        "key": "lux",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "lx",
        "icon": "mdi:brightness-6",
        "value_type": "float",
    },
    {
        "name": "Heart Rate",
        "key": "heartrate_value",
        "unit": "bpm",
        "icon": "mdi:heart-pulse",
        "value_type": "int",
    },
    {
        "name": "Respiration Rate",
        "key": "respiration_rate_value",
        "unit": "rpm",
        "icon": "mdi:lungs",
        "value_type": "int",
    },
    {
        "name": "Body Movement",
        "key": "body_movement_value",
        "icon": "mdi:run",
        "value_type": "int",
    },
    {
        "name": "Sleep State",
        "key": "sleep_state",
        "icon": "mdi:power-sleep",
        "value_type": "str",
    },
    {
        "name": "Operating Mode",
        "key": "set_device_mode4",
        "icon": "mdi:cog",
        "value_map": FP2_MODE_LABELS,
    },
    {
        "name": "View Zoom",
        "key": "view_zoom",
        "icon": "mdi:magnify-scan",
        "value_map": FP2_VIEW_MODES,
    },
    {
        "name": "Mounting Position",
        "key": "mounting_position",
        "icon": "mdi:wall",
        "value_map": FP2_MOUNTING_POSITIONS,
    },
    {
        "name": "Installation Angle",
        "key": "installation_angle",
        "icon": "mdi:rotate-3d-variant",
        "value_map": FP2_INSTALLATION_ANGLES,
    },
    {
        "name": "Attitude Status",
        "key": "attitude_status",
        "icon": "mdi:axis-arrow",
    },
]

FP2_SETTINGS_SENSORS_DEF = [
    {
        "name": "Presence Sensitivity",
        "key": "presence_detection_sens",
        "icon": "mdi:account-eye",
        "value_map": FP2_SETTING_VALUE_MAPS["presence_detection_sens"],
    },
    {
        "name": "Proximity Distance",
        "key": "proximity_sensing_dist",
        "icon": "mdi:signal-distance-variant",
        "value_map": FP2_SETTING_VALUE_MAPS["proximity_sensing_dist"],
    },
    {
        "name": "Fall Detection Sensitivity",
        "key": "fall_detection_sens",
        "icon": "mdi:human-female-fall",
        "value_map": FP2_SETTING_VALUE_MAPS["fall_detection_sens"],
    },
    {
        "name": "Reverse Coordinate Direction",
        "key": "reverse_coordinate_dir",
        "icon": "mdi:axes-arrow",
        "value_map": FP2_SETTING_VALUE_MAPS["reverse_coordinate_dir"],
    },
    {
        "name": "Detection Direction",
        "key": "detection_dir",
        "icon": "mdi:axis-z-arrow",
        "value_map": FP2_SETTING_VALUE_MAPS["detection_dir"],
    },
    {
        "name": "AI Person Detection",
        "key": "ai_person_det",
        "icon": "mdi:account-search",
        "value_map": FP2_SETTING_VALUE_MAPS["ai_person_det"],
    },
    {
        "name": "Anti-light Pollution Mode",
        "key": "anti_light_poll",
        "icon": "mdi:white-balance-sunny",
        "value_map": FP2_SETTING_VALUE_MAPS["anti_light_poll"],
    },
]

FP2_SENSOR_SPECS = [
    *FP2_STATUS_SENSORS_DEF,
    *FP2_SETTINGS_SENSORS_DEF,
]
