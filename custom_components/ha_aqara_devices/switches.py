from typing import Dict, Any

VIDEO_SWITCH_DEF: Dict[str, Any] = {
    "name": "Video",
    "icon": "mdi:video",
    "inApp": "camera_active",
    "api": "set_video",       
    "on_data":  {"set_video": 1},
    "off_data": {"set_video": 0},
}

DETECT_HUMAN_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Human",
    "icon": "mdi:motion-sensor",
    "inApp": "human_detect_enable", 
    "api": "humans_track_enable",  
    "on_data":  {
        "human_detect_enable": "1",
        "humans_track_enable": "1",
        "pets_track_enable": "0",
        "ptz_cruise_enable": "0",
        "gesture_detect_enable": "0",
    },
    "off_data": {
        "humans_track_enable": "0",
    },
}

DETECT_PET_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Pet",
    "icon": "mdi:paw",
    "inApp": "pets_track_enable", 
    "api": "pets_track_enable",  
    "on_data":  {
        "pets_track_enable": "1",
        "pets_detect_enable": "1",
        "humans_track_enable": "0",
        "ptz_cruise_enable": "0",
        "gesture_detect_enable": "0",
    },
    "off_data": {
        "pets_track_enable": "0",
    },
}

DETECT_GESTURE_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Gesture",
    "icon": "mdi:hand-wave",
    "inApp": "gesture_detect_enable", 
    "api": "gesture_detect_enable",  
    "on_data":  {
        "pets_track_enable": "0",
        "pets_detect_enable": "0",
        "humans_track_enable": "0",
        "ptz_cruise_enable": "0",
        "gesture_detect_enable": "1",
        "face_detect_enable": "0",
    },
    "off_data": {
        "gesture_detect_enable": "0",
    },
}

DETECT_FACE_SWITCH_DEF: Dict[str, Any] = {
    "name": "Detect Face",
    "icon": "mdi:face-recognition",
    "inApp": "face_detect_enable", 
    "api": "face_detect_enable",  
    "on_data":  {
        "pets_track_enable": "0",
        "pets_detect_enable": "0",
        "humans_track_enable": "0",
        "ptz_cruise_enable": "0",
        "gesture_detect_enable": "0",
        "face_detect_enable": "1",
    },
    "off_data": {
        "face_detect_enable": "0",
    },
}

MODE_CRUISE_SWITCH_DEF: Dict[str, Any] = {
    "name": "Mode Cruise",
    "icon": "mdi:autorenew",
    "inApp": "ptz_cruise_enable", 
    "api": "ptz_cruise_enable",  
    "on_data":  {
        "pets_track_enable": "0",
        "pets_detect_enable": "0",
        "humans_track_enable": "0",
        "ptz_cruise_enable": "1",
        "gesture_detect_enable": "0",
        "face_detect_enable": "0",
    },
    "off_data": {
        "ptz_cruise_enable": "0",
    },
}

ALL_SWITCHES_DEF = [
    VIDEO_SWITCH_DEF,
    DETECT_HUMAN_SWITCH_DEF,
    DETECT_PET_SWITCH_DEF,
    DETECT_GESTURE_SWITCH_DEF,
    DETECT_FACE_SWITCH_DEF,
    MODE_CRUISE_SWITCH_DEF,
]