from typing import Dict, Any

VIDEO_SWITCH_DEF: Dict[str, Any] = {
    "name": "Video",
    "icon": "mdi:video",
    "inApp": "camera_active",
    "api": "14.74.85",
    "on_data":  {"14.74.85": 1},
    "off_data": {"14.74.85": 0},
}

DETECT_HUMAN_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Human",
    "icon": "mdi:motion-sensor",
    "inApp": "human_detect_enable", 
    "api": "14.77.85",
    "on_data":  {
        "14.77.85": "1",
        "14.78.85": "0",
        "14.76.85": "0",
    },
    "off_data": {
        "14.77.85": "0",
    },
}

DETECT_PET_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Pet",
    "icon": "mdi:paw",
    "inApp": "pets_track_enable", 
    "api": "14.78.85",
    "on_data":  {
        "14.78.85": "1",
        "14.77.85": "0",
        "14.76.85": "0",
    },
    "off_data": {
        "14.78.85": "0",
    },
}

DETECT_GESTURE_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Gesture",
    "icon": "mdi:hand-wave",
    "inApp": "gesture_detect_enable", 
    "api": "14.76.85",
    "on_data":  {
        "14.78.85": "0",
        "14.77.85": "0",
        "14.76.85": "1",
        "14.75.85": "0",
    },
    "off_data": {
        "14.76.85": "0",
    },
}

DETECT_FACE_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Face",
    "icon": "mdi:face-recognition",
    "inApp": "face_detect_enable", 
    "api": "14.75.85",
    "on_data":  {
        "14.78.85": "0",
        "14.77.85": "0",
        "14.76.85": "0",
        "14.75.85": "1",
    },
    "off_data": {
        "14.75.85": "0",
    },
}

ALL_SWITCHES_DEF = [
    VIDEO_SWITCH_DEF,
    DETECT_HUMAN_SWITCH_DEF,
    DETECT_PET_SWITCH_DEF,
    DETECT_GESTURE_SWITCH_DEF,
    DETECT_FACE_SWITCH_DEF,
]

M100_GATEWAY_DELETION_SETTING = {
    "name": "Sub-device Deletion Protection",
    "icon": "mdi:shield-remove",
    "inApp": "gateway_deletion_setting",
    "api": "8.0.2158",
    "on_data": {"8.0.2158": 1},
    "off_data": {"8.0.2158": 0},
    "value_type": "bool",
}

M100_SWITCHES_DEF = [
    M100_GATEWAY_DELETION_SETTING,
]


def _g2h_pro_switch(name: str, icon: str, in_app: str, api: str) -> Dict[str, Any]:
    return {
        "name": name,
        "icon": icon,
        "inApp": in_app,
        "api": api,
        "on_data": {api: 1},
        "off_data": {api: 0},
        "value_type": "bool",
    }


G2H_PRO_SOUND_DETECTION = _g2h_pro_switch(
    "Sound Detection",
    "mdi:volume-source",
    "soundtrigger_enable",
    "14.119.85",
)
G2H_PRO_TIMED_SLEEP = _g2h_pro_switch(
    "Timed Sleep",
    "mdi:sleep",
    "time_sleep_enable",
    "14.125.85",
)
G2H_PRO_MOTION_PUSH = _g2h_pro_switch(
    "Motion Push",
    "mdi:motion-sensor",
    "md_push_enable",
    "4.51.85",
)
G2H_PRO_MOTION_DETECTION = _g2h_pro_switch(
    "Motion Detection",
    "mdi:motion-sensor",
    "mdtrigger_enable",
    "14.70.85",
)
G2H_PRO_INDICATOR_LIGHT = _g2h_pro_switch(
    "Indicator Light",
    "mdi:led-on",
    "device_night_tip_light",
    "8.0.2032",
)
G2H_PRO_TIMELAPSE_PUSH = _g2h_pro_switch(
    "Timelapse Push",
    "mdi:camera-timer",
    "camera_timelapse_push",
    "4.28.85",
)
G2H_PRO_SOUND_PUSH = _g2h_pro_switch(
    "Sound Push",
    "mdi:volume-source",
    "cry_push_enable",
    "4.53.85",
)
G2H_PRO_DEVICE_OFFLINE_PUSH = _g2h_pro_switch(
    "Device Offline Push",
    "mdi:lan-disconnect",
    "device_offline_push_enable",
    "4.89.85",
)
G2H_PRO_MOTION_RECORDING = _g2h_pro_switch(
    "Motion Recording",
    "mdi:record-rec",
    "md_record_enable",
    "4.50.85",
)
G2H_PRO_TIMELAPSE = _g2h_pro_switch(
    "Timelapse",
    "mdi:camera-timer",
    "camera_timelapse_switch",
    "4.27.85",
)
G2H_PRO_SOUND_RECORDING = _g2h_pro_switch(
    "Sound Recording",
    "mdi:record-rec",
    "cry_record_enable",
    "4.52.85",
)
G2H_PRO_CAMERA = _g2h_pro_switch(
    "Camera",
    "mdi:video",
    "set_video",
    "14.74.85",
)

G2H_PRO_SWITCHES_DEF = [
    G2H_PRO_SOUND_DETECTION,
    G2H_PRO_TIMED_SLEEP,
    G2H_PRO_MOTION_PUSH,
    G2H_PRO_MOTION_DETECTION,
    G2H_PRO_INDICATOR_LIGHT,
    G2H_PRO_TIMELAPSE_PUSH,
    G2H_PRO_SOUND_PUSH,
    G2H_PRO_DEVICE_OFFLINE_PUSH,
    G2H_PRO_MOTION_RECORDING,
    G2H_PRO_TIMELAPSE,
    G2H_PRO_SOUND_RECORDING,
    G2H_PRO_CAMERA,
]


def _g410_switch(name: str, icon: str, in_app: str, api: str) -> Dict[str, Any]:
    return {
        "name": name,
        "icon": icon,
        "inApp": in_app,
        "api": api,
        "on_data": {api: 1},
        "off_data": {api: 0},
        "value_type": "bool",
    }


G410_HIGH_TEMP_ALARM = _g410_switch(
    "High Temperature Alarm",
    "mdi:thermometer-alert",
    "high_temp_alarm",
    "4.67.85",
)
G410_FACE_PUSH = _g410_switch(
    "Face Recognition Push",
    "mdi:face-recognition",
    "face_push_enable",
    "4.55.85",
)
G410_SCHEDULED_SLEEP = _g410_switch(
    "Scheduled Sleep",
    "mdi:sleep",
    "time_sleep_enable",
    "14.125.85",
)
G410_INDICATOR_LIGHT = _g410_switch(
    "Indicator Light",
    "mdi:led-on",
    "device_night_tip_light",
    "8.0.2032",
)
G410_ANTI_TAMPER_ALARM = _g410_switch(
    "Anti-Tamper Alarm",
    "mdi:shield-alert",
    "damage_alarm",
    "4.66.85",
)
G410_FACE_RECORDING = _g410_switch(
    "Face Recording",
    "mdi:record-rec",
    "face_record_enable",
    "4.54.85",
)
G410_DOORBELL_NOTIFICATION = _g410_switch(
    "Doorbell Notification",
    "mdi:bell-ring",
    "doorbell_push_enable",
    "4.154.85",
)
G410_LOW_TEMP_ALARM = _g410_switch(
    "Low Temperature Alarm",
    "mdi:thermometer-alert",
    "low_temp_alarm",
    "4.68.85",
)
G410_DOORBELL_RECORDING = _g410_switch(
    "Doorbell Recording",
    "mdi:record-rec",
    "doorbell_record_enable",
    "4.138.85",
)

G410_SWITCHES_DEF = [
    G410_HIGH_TEMP_ALARM,
    G410_FACE_PUSH,
    G410_SCHEDULED_SLEEP,
    G410_INDICATOR_LIGHT,
    G410_ANTI_TAMPER_ALARM,
    G410_FACE_RECORDING,
    G410_DOORBELL_NOTIFICATION,
    G410_LOW_TEMP_ALARM,
    G410_DOORBELL_RECORDING,
]
