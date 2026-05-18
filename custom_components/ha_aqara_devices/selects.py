ALARM_BELL_INDEX_OPTIONS = [
    (10000, "Default"),
    (0, "Police car sound 1"),
    (1, "Police car sound 2"),
    (2, "Safety accident sound"),
    (3, "Missile countdown"),
    (4, "Ghost scream"),
    (5, "Sniper rifle"),
    (6, "Battle sound"),
    (7, "Air raid alarm"),
    (8, "Dog barking"),
]

DOORBELL_BELL_INDEX_OPTIONS = [
    (10000, "Default"),
    (0, "Index 0"),
    (1, "Index 1"),
    (2, "Index 2"),
    (3, "Index 3"),
    (4, "Index 4"),
    (5, "Index 5"),
    (6, "Index 6"),
    (7, "Index 7"),
    (8, "Index 8"),
]

M3_GATEWAY_LANGUAGE = {
    "name": "Gateway Language",
    "icon": "mdi:translate",
    "inApp": "gateway_language",
    "api": "14.10.85",
    "options": [
        (0, "Chinese"),
        (1, "English"),
    ],
    "value_type": "int",
    "default": None,
}

M3_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M3_DOORBELL_BELL_INDEX = {
    "name": "Doorbell Ringtone",
    "icon": "mdi:doorbell",
    "inApp": "doorbell_bell_index",
    "api": "14.2.85",
    "options": DOORBELL_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M3_SELECTS_DEF = [
    M3_GATEWAY_LANGUAGE,
    M3_ALARM_BELL_INDEX,
    M3_DOORBELL_BELL_INDEX,
]

M100_GATEWAY_LANGUAGE = {
    "name": "Gateway Language",
    "icon": "mdi:translate",
    "inApp": "gateway_language",
    "api": "14.10.85",
    "options": [
        (1, "Chinese"),
        (2, "English"),
    ],
    "value_type": "int",
    "default": None,
}

M100_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M100_DOORBELL_BELL_INDEX = {
    "name": "Doorbell Ringtone",
    "icon": "mdi:doorbell",
    "inApp": "doorbell_bell_index",
    "api": "14.2.85",
    "options": DOORBELL_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M100_SELECTS_DEF = [
    M100_GATEWAY_LANGUAGE,
    M100_ALARM_BELL_INDEX,
    M100_DOORBELL_BELL_INDEX,
]

G410_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

G410_IMAGE_FLIP = {
    "name": "Screen Flip",
    "icon": "mdi:flip-horizontal",
    "inApp": "image_flip",
    "api": "14.68.85",
    "options": [
        (0, "Normal"),
        (1, "Flip Horizontally"),
        (2, "Flip Vertically"),
        (3, "Flip Horizontally and Vertically"),
    ],
    "value_type": "int",
    "default": None,
}

G410_CAMERA_MODE = {
    "name": "Camera Mode",
    "icon": "mdi:video",
    "inApp": "ctrl_camera",
    "api": "4.8.85",
    "options": [
        (0, "Off"),
        (1, "On"),
        (255, "Always On"),
    ],
    "value_type": "int",
    "default": None,
}

G410_SELECTS_DEF = [
    G410_ALARM_BELL_INDEX,
    G410_IMAGE_FLIP,
    G410_CAMERA_MODE,
]
