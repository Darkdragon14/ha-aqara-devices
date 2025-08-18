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

ALL_SWITCHES_DEF = [VIDEO_SWITCH_DEF, DETECT_HUMAN_SWITCH_DEF]