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
    "api": "gateway_language",
    "options": [
        (1, "Chinese"),
        (2, "English"),
    ],
    "value_type": "int",
    "default": None,
}

M3_ALARM_BELL_INDEX = {
    "name": "Alarm Ringtone",
    "icon": "mdi:bell",
    "inApp": "alarm_bell_index",
    "api": "alarm_bell_index",
    "options": ALARM_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M3_DOORBELL_BELL_INDEX = {
    "name": "Doorbell Ringtone",
    "icon": "mdi:doorbell",
    "inApp": "doorbell_bell_index",
    "api": "doorbell_bell_index",
    "options": DOORBELL_BELL_INDEX_OPTIONS,
    "value_type": "int",
    "default": None,
}

M3_SELECTS_DEF = [
    M3_GATEWAY_LANGUAGE,
    M3_ALARM_BELL_INDEX,
    M3_DOORBELL_BELL_INDEX,
]
