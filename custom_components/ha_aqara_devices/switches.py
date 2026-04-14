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
