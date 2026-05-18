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
    _gesture_sensor("Gesture V sign both hands", "gesture_v_sign_both_hands", "gesture_101", "101"),
    _gesture_sensor("Gesture Four both hands", "gesture_four_both_hands", "gesture_102", "102"),
    _gesture_sensor("Gesture High Five both hands", "gesture_high_five_both_hands", "gesture_103", "103"),
    _gesture_sensor("Gesture Finger Gun both hands", "gesture_finger_gun_both_hands", "gesture_104", "104"),
    _gesture_sensor("Gesture OK both hands", "gesture_ok_both_hands", "gesture_105", "105"),
]

G3_MOTION_EVENT = {
    "name": "Motion Event",
    "icon": "mdi:motion-sensor",
    "inApp": "mdtrigger",
    "api": "3.21.85",
    "device_class": "motion",
    "value_type": "event",
    "hold_seconds": 10,
    "queryable": False,
}


ALL_BINARY_SENSORS_DEF = [
    NIGHT_VISION,
    G3_MOTION_EVENT,
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

M100_DEVICE_ONLINE_STATUS = {
    "name": "Device Online",
    "icon": "mdi:lan-connect",
    "inApp": "device_online_status",
    "api": "8.0.2045",
    "device_class": "connectivity",
    "value_type": "bool",
}

M100_BINARY_SENSORS_DEF = [
    M100_DEVICE_ONLINE_STATUS,
]

G410_DOORBELL_RING = {
    "name": "Doorbell Ring",
    "icon": "mdi:doorbell-video",
    "inApp": "bell_ring",
    "api": "13.12.85",
    "device_class": "motion",
    "value_type": "event",
    "hold_seconds": 10,
}

G410_ALARM_STATUS = {
    "name": "Alarm Status",
    "icon": "mdi:alarm-light",
    "inApp": "alarm_status",
    "api": "14.1.111",
    "device_class": "safety",
    "value_type": "bool",
}

G410_BINARY_SENSORS_DEF = [
    G410_DOORBELL_RING,
    G410_ALARM_STATUS,
]
