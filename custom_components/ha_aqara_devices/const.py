from __future__ import annotations

DOMAIN = "ha_aqara_devices"
PLATFORMS: list[str] = ["switch", "button", "binary_sensor", "number", "sensor", "select"]  # only services for this MVP

# Endpoint used for attribute write/query
REQUEST_PATH = "/app/v1.0/lumi/res/write"  # per AqaraPOST examples
QUERY_PATH = "/app/v1.0/lumi/res/query"
HISTORY_PATH = "/app/v1.0/lumi/res/history/log"
DEVICES_PATH = "/app/v1.0/lumi/app/position/device/query"
OPERATE_PATH = "/app/v1.0/lumi/devex/camera/operate"
RESOURCE_QUERY_PATH = "/app/v1.0/lumi/res/query/by/resourceId"

# Minimal area map (extend later as needed)
AREAS = {
    "EU": {"server": "https://rpc-ger.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "US": {"server": "https://aiot-rpc-usa.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "CN": {"server": "https://aiot-rpc.aqara.cn", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "RU": {"server": "https://rpc-ru.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
    "OTHER": {"server": "https://aiot-rpc-usa.aqara.com", "appid": "444c476ef7135e53330f46e7", "appkey": "NULL"},
}

G3_MODEL = "lumi.camera.gwpgl1"
M3_MODELS = {"lumi.gateway.acn012", "lumi.gateway.agl004"}

G3_DEVICE_LABEL = "Aqara G3"
M3_DEVICE_LABEL = "Aqara Hub M3"
FP2_MODEL = "lumi.motion.agl001"

FP2_ZONE_COUNT = 30
FP2_MINUTE_ZONE_COUNT = 7

FP2_BASE_STATUS_ATTRS: list[str] = [
    "heartrate_value",
    "respiration_rate_value",
    "sleep_state",
    "body_movement_value",
    "lux",
    "installation_angle",
    "set_device_mode4",
    "device_offline_status",
    "view_zoom",
    "mounting_position",
    "attitude_status",
]

FP2_GLOBAL_COUNT_ATTRS: list[str] = [
    "all_zone_statistics",
    "people_counting",
    "people_counting_by_mins",
]

FP2_ZONE_STATISTICS_ATTRS: list[str] = [
    f"zone{index}_statistics" for index in range(1, FP2_ZONE_COUNT + 1)
]

FP2_ZONE_MINUTE_COUNT_ATTRS: list[str] = [
    f"zone{index}_people_counting_by_mins"
    for index in range(1, FP2_MINUTE_ZONE_COUNT + 1)
]

FP2_ZONE_PRESENCE_ATTRS: list[str] = [
    f"detection_area{index}" for index in range(1, FP2_ZONE_COUNT + 1)
]

FP2_STATUS_ATTRS: list[str] = [
    *FP2_BASE_STATUS_ATTRS,
    *FP2_GLOBAL_COUNT_ATTRS,
    *FP2_ZONE_STATISTICS_ATTRS,
    *FP2_ZONE_MINUTE_COUNT_ATTRS,
    *FP2_ZONE_PRESENCE_ATTRS,
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

# Public key used to encrypt MD5(password) (same as token generator script)
AQARA_RSA_PUBKEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCG46slB57013JJs4Vvj5cVyMpR
9b+B2F+YJU6qhBEYbiEmIdWpFPpOuBikDs2FcPS19MiWq1IrmxJtkICGurqImRUt
4lP688IWlEmqHfSxSRf2+aH0cH8VWZ2OaZn5DWSIHIPBF2kxM71q8stmoYiV0oZs
rZzBHsMuBwA4LQdxBwIDAQAB
-----END PUBLIC KEY-----
"""
