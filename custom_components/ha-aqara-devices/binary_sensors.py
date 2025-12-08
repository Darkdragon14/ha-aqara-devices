NIGHT_VISION = {
    "name": "Night vision",
    "translation_key": "night_vision",
    "icon": "mdi:shield-moon",
    "inApp": "night_vision",
    "api": "device_night_tip_light",
}

GESTURE_RESOURCE_ID = "13.96.85"
GESTURE_HOLD_SECONDS = 10


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
