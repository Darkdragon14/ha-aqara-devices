from __future__ import annotations

DOMAIN = "ha_aqara_devices"
PLATFORMS: list[str] = ["switch", "button", "binary_sensor", "number", "sensor", "select"]  # only services for this MVP

CONF_BRIDGE_URL = "bridge_url"
CONF_BRIDGE_TOKEN = "bridge_token"
CONF_APP_ID = "app_id"
CONF_APP_KEY = "app_key"
CONF_KEY_ID = "key_id"
DEFAULT_BRIDGE_URL = "http://aqara-rocketmq-bridge:8080"
BRIDGE_SANITY_INTERVAL_SECONDS = 300
BRIDGE_UNAVAILABLE_AFTER_FAILURES = 3

OPEN_API_PATH = "/v3.0/open/api"
AQARA_MQ_SERVER = "3rd-subscription.aqara.cn:9876"
DEFAULT_ACCESS_TOKEN_VALIDITY = "7d"
TOKEN_REFRESH_STARTUP_MARGIN_SECONDS = 600
TOKEN_REFRESH_REQUEST_MARGIN_SECONDS = 300

# Aqara Open API servers by region
AREAS = {
    "EU": {"server": "https://open-ger.aqara.com"},
    "US": {"server": "https://open-usa.aqara.com"},
    "CN": {"server": "https://open-cn.aqara.com"},
    "RU": {"server": "https://open-ru.aqara.com"},
    "KR": {"server": "https://open-kr.aqara.com"},
    "SG": {"server": "https://open-sg.aqara.com"},
    "OTHER": {"server": "https://open-usa.aqara.com"},
}

AREA_OPTIONS = list(AREAS.keys())

G3_MODEL = "lumi.camera.gwpgl1"
FP2_MODEL = "lumi.motion.agl001"
FP300_MODEL = "lumi.sensor_occupy.agl8"
G3_MODELS = {"lumi.camera.gwpgl1", "lumi.camera.gwpagl01"}
M3_MODELS = {"lumi.gateway.acn012", "lumi.gateway.agl004"}
PRESENCE_MODELS = {FP2_MODEL, FP300_MODEL}

G3_DEVICE_LABEL = "Aqara G3"
M3_DEVICE_LABEL = "Aqara Hub M3"
FP2_DEVICE_LABEL = "Aqara FP2"
FP300_DEVICE_LABEL = "Presence Multi-Sensor FP300"

FP2_FAST_INTERVAL_SECONDS = 2
FP2_PRESENCE_INTERVAL_SECONDS = 5
FP300_FAST_INTERVAL_SECONDS = 5
PRESENCE_MEDIUM_INTERVAL_SECONDS = 30
PRESENCE_SLOW_INTERVAL_SECONDS = 300
PRESENCE_UNAVAILABLE_AFTER_FAILURES = 3
FP2_FAST_UNAVAILABLE_AFTER_FAILURES = 5
FP2_PRESENCE_UNAVAILABLE_AFTER_FAILURES = 8
FP300_FAST_UNAVAILABLE_AFTER_FAILURES = 5

FP300_FAST_STATUS_ATTRS: list[str] = [
    "3.51.85",
]

FP300_MEDIUM_STATUS_ATTRS: list[str] = [
    "0.1.85",
    "0.2.85",
    "0.3.85",
]

FP300_SLOW_STATUS_ATTRS: list[str] = [
    "8.0.2001",
]

FP300_CORE_STATUS_ATTRS: list[str] = [
    *FP300_FAST_STATUS_ATTRS,
    *FP300_MEDIUM_STATUS_ATTRS,
    *FP300_SLOW_STATUS_ATTRS,
]

FP2_FAST_STATUS_BASE_ATTRS: list[str] = [
    "8.0.2045",
    "13.11.85",
]

FP2_MEDIUM_STATUS_BASE_ATTRS: list[str] = [
    "0.8.85",
    "0.9.85",
    "13.106.85",
    "0.4.85",
]

FP2_SLOW_STATUS_ATTRS: list[str] = [
    "13.35.85",
    "14.49.85",
    "14.57.85",
    "13.70.85",
]

FP2_ZONE_COUNT = 30
FP2_MINUTE_ZONE_COUNT = 7

FP2_GLOBAL_COUNT_ATTRS: list[str] = [
    "13.120.85",
    "0.60.85",
    "0.61.85",
]

FP2_ZONE_STATISTICS_ATTRS: list[str] = [
    f"13.{120 + index}.85" for index in range(1, FP2_ZONE_COUNT + 1)
]

FP2_ZONE_MINUTE_COUNT_ATTRS: list[str] = [
    f"0.{120 + index}.85"
    for index in range(1, FP2_MINUTE_ZONE_COUNT + 1)
]

FP2_ZONE_PRESENCE_ATTRS: list[str] = [
    f"3.{index}.85" for index in range(1, FP2_ZONE_COUNT + 1)
]

FP2_FAST_STATUS_ATTRS: list[str] = [
    *FP2_FAST_STATUS_BASE_ATTRS,
    *FP2_ZONE_PRESENCE_ATTRS,
]

FP2_FAST_RESOURCE_KEY_MAP = {
    "8.0.2045": "device_offline_status",
    "13.11.85": "body_movement_value",
    **{
        f"3.{index}.85": f"detection_area{index}"
        for index in range(1, FP2_ZONE_COUNT + 1)
    },
}

FP2_MEDIUM_STATUS_ATTRS: list[str] = [
    *FP2_MEDIUM_STATUS_BASE_ATTRS,
    *FP2_GLOBAL_COUNT_ATTRS,
    *FP2_ZONE_STATISTICS_ATTRS,
    *FP2_ZONE_MINUTE_COUNT_ATTRS,
]

FP2_STATUS_ATTRS: list[str] = [
    *FP2_FAST_STATUS_ATTRS,
    *FP2_MEDIUM_STATUS_ATTRS,
    *FP2_SLOW_STATUS_ATTRS,
]

FP2_RESOURCE_IDS = [
    "14.30.85",
    "14.55.85",
    "14.51.85",
    "14.1.85",
    "14.47.85",
    "4.23.85",
    "4.72.85",
]

FP2_RESOURCE_KEY_MAP = {
    "14.30.85": "fall_detection_sens",
    "14.55.85": "detection_dir",
    "14.51.85": "reverse_coordinate_dir",
    "14.1.85": "presence_detection_sens",
    "14.47.85": "proximity_sensing_dist",
    "4.23.85": "anti_light_poll",
    "4.72.85": "ai_person_det",
}

FP2_PRESENCE_RESOURCES = ["3.51.85", "3.52.85"]

FP2_MODE_LABELS = {
    "3": "zone_detection",
    "5": "fall_detection",
    "9": "sleep_monitoring",
}

FP2_VIEW_MODES = {
    "0": "full",
    "1": "adaptive",
}

FP2_MOUNTING_POSITIONS = {
    "1": "wall",
    "2": "left_corner",
    "3": "right_corner",
}

FP2_INSTALLATION_ANGLES = {
    "0": "face_up",
    "1": "oblique",
    "2": "oblique",
    "3": "horizontal",
    "4": "horizontal",
    "5": "face_down",
    "6": "oblique",
    "7": "oblique",
    "8": "oblique",
}

FP2_SETTING_VALUE_MAPS = {
    "fall_detection_sens": {"1": "low", "2": "medium", "3": "high"},
    "presence_detection_sens": {"1": "low", "2": "medium", "3": "high"},
    "proximity_sensing_dist": {"0": "far", "1": "medium", "2": "close"},
    "reverse_coordinate_dir": {"0": "disable", "1": "enable", "2": "auto"},
    "anti_light_poll": {"0": "disable", "1": "enable"},
    "ai_person_det": {"0": "disable", "1": "enable"},
    "detection_dir": {"0": "default", "1": "left_right"},
}
