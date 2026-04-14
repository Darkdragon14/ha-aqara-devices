NIGHT_VISION = {
    "name": "Night vision",
    "translation_key": "night_vision",
    "icon": "mdi:shield-moon",
    "inApp": "night_vision",
    "api": "8.0.2032",
}

GESTURE_RESOURCE_ID = "13.96.85"
GESTURE_HOLD_SECONDS = 5


def _gesture_sensor(name: str, translation_key: str, in_app: str, value: str) -> dict:
    return {
        "name": name,
        "translation_key": translation_key,
        "icon": "mdi:gesture",
        "inApp": in_app,
        "history_resource": GESTURE_RESOURCE_ID,
        "history_value": value,
        "value_type": "timestamp",
        "hold_seconds": GESTURE_HOLD_SECONDS,
        "device_class": "motion",
    }


GESTURE_SENSORS = [
    _gesture_sensor("Gesture V sign", "gesture_v_sign", "gesture_2", "2"),
    _gesture_sensor("Gesture Four", "gesture_four", "gesture_4", "4"),
    _gesture_sensor("Gesture High Five", "gesture_high_five", "gesture_5", "5"),
    _gesture_sensor("Gesture Finger Gun", "gesture_finger_gun", "gesture_6", "6"),
    _gesture_sensor("Gesture OK", "gesture_ok", "gesture_ok", "10"),
]


ALL_BINARY_SENSORS_DEF = [
    NIGHT_VISION,
    *GESTURE_SENSORS,
]

M3_ALARM_STATUS = {
    "name": "Alarm Status",
    "icon": "mdi:alarm-bell",
    "inApp": "alarm_status",
    "api": "14.1.111",
    "device_class": "safety",
    "value_type": "bool",
}

M3_DEVICE_ONLINE_STATUS = {
    "name": "Device Online",
    "icon": "mdi:lan-connect",
    "inApp": "device_online_status",
    "api": "8.0.2045",
    "device_class": "connectivity",
    "value_type": "bool",
}

M3_BINARY_SENSORS_DEF = [
    M3_ALARM_STATUS,
    M3_DEVICE_ONLINE_STATUS,
]
