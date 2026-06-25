ALARM_BELL_INDEX_OPTIONS = [
    (10000, "default"),
    (0, "police_car_1"),
    (1, "police_car_2"),
    (2, "safety_accident"),
    (3, "missile_countdown"),
    (4, "ghost_scream"),
    (5, "sniper_rifle"),
    (6, "battle"),
    (7, "air_raid_alarm"),
    (8, "dog_barking"),
]

DOORBELL_BELL_INDEX_OPTIONS = [
    (10000, "default"),
    (0, "index_0"),
    (1, "index_1"),
    (2, "index_2"),
    (3, "index_3"),
    (4, "index_4"),
    (5, "index_5"),
    (6, "index_6"),
    (7, "index_7"),
    (8, "index_8"),
]

M3_GATEWAY_LANGUAGE = {
    "name": "Gateway Language",
    "translation_key": "gateway_language",
    "icon": "mdi:translate",
    "inApp": "gateway_language",
    "api": "14.10.85",
    "options": [
        (0, "chinese"),
        (1, "english"),
    ],
    "value_type": "int",
    "default": None,
}

M3_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "translation_key": "alarm_ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M3_DOORBELL_BELL_INDEX = {
    "name": "Doorbell Ringtone",
    "translation_key": "doorbell_ringtone",
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
    "translation_key": "gateway_language",
    "icon": "mdi:translate",
    "inApp": "gateway_language",
    "api": "14.10.85",
    "options": [
        (1, "chinese"),
        (2, "english"),
    ],
    "value_type": "int",
    "default": None,
}

M100_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "translation_key": "alarm_ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M100_DOORBELL_BELL_INDEX = {
    "name": "Doorbell Ringtone",
    "translation_key": "doorbell_ringtone",
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

M200_GATEWAY_LANGUAGE = {
    "name": "Gateway Language",
    "translation_key": "gateway_language",
    "icon": "mdi:translate",
    "inApp": "gateway_language",
    "api": "14.10.85",
    "options": [
        (1, "chinese"),
        (2, "english"),
    ],
    "value_type": "int",
    "default": None,
}

M200_ALERT_RINGTONE = {
    "name": "Alert Ringtone",
    "translation_key": "alarm_ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M200_AC_MODE = {
    "name": "AC Mode",
    "translation_key": "ac_mode",
    "icon": "mdi:air-conditioner",
    "inApp": "ac_mode",
    "api": "14.25.85",
    "options": [
        (0, "unconfigured"),
        (1, "air_conditioner_with_socket"),
        (2, "air_conditioner_without_socket"),
        (3, "infrared_water_heater"),
        (4, "16a_socket"),
    ],
    "value_type": "int",
    "default": None,
}

M200_SELECTS_DEF = [
    M200_GATEWAY_LANGUAGE,
    M200_ALERT_RINGTONE,
    M200_AC_MODE,
]

G410_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "translation_key": "alarm_ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "14.1.85",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

G410_IMAGE_FLIP = {
    "name": "Screen Flip",
    "translation_key": "screen_flip",
    "icon": "mdi:flip-horizontal",
    "inApp": "image_flip",
    "api": "14.68.85",
    "options": [
        (0, "normal"),
        (1, "flip_horizontally"),
        (2, "flip_vertically"),
        (3, "flip_horizontally_and_vertically"),
    ],
    "value_type": "int",
    "default": None,
}

G410_CAMERA_MODE = {
    "name": "Camera Mode",
    "translation_key": "camera_mode",
    "icon": "mdi:video",
    "inApp": "ctrl_camera",
    "api": "4.8.85",
    "options": [
        (0, "off"),
        (1, "on"),
        (255, "always_on"),
    ],
    "value_type": "int",
    "default": None,
}

G410_SELECTS_DEF = [
    G410_ALARM_BELL_INDEX,
    G410_IMAGE_FLIP,
    G410_CAMERA_MODE,
]

G4_SELECTS_DEF = [
    G410_IMAGE_FLIP,
]

FP300_WORK_MODE = {
    "name": "Work Mode",
    "translation_key": "work_mode",
    "icon": "mdi:radar",
    "inApp": "work_mode",
    "api": "14.59.85",
    "poll_group": "slow",
    "options": [
        (0, "radar_infrared"),
        (1, "radar_only"),
        (2, "infrared_only"),
    ],
    "value_type": "int",
    "default": None,
}

FP300_SELECTS_DEF = [
    FP300_WORK_MODE,
]
