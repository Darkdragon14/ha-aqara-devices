VOLUME = {
    "name": "Volume",
    "icon": "mdi:volume-high",
    "inApp": "volume",
    "api": "14.11.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer"
}

ALL_NUMBERS_DEF = [
    VOLUME
]

M3_SYSTEM_VOLUME = {
    "name": "System Volume",
    "icon": "mdi:volume-high",
    "inApp": "system_volume",
    "api": "14.11.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer"
}

M3_ALARM_BELL_VOLUME = {
    "name": "Alarm Volume",
    "icon": "mdi:bell-ring",
    "inApp": "alarm_bell_volume",
    "api": "14.1.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer"
}

M3_DOORBELL_BELL_VOLUME = {
    "name": "Doorbell Volume",
    "icon": "mdi:doorbell",
    "inApp": "doorbell_bell_volume",
    "api": "14.2.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer"
}

M3_ALARM_TIME_LENGTH = {
    "name": "Alarm Duration",
    "icon": "mdi:timer",
    "inApp": "alarm_time_length",
    "api": "14.1.113",
    "min": -1,
    "max": 255,
    "step": 1,
    "type": "integer"
}

M3_DOORBELL_TIME_LENGTH = {
    "name": "Doorbell Duration",
    "icon": "mdi:timer",
    "inApp": "doorbell_time_length",
    "api": "14.2.113",
    "min": -1,
    "max": 255,
    "step": 1,
    "type": "integer"
}

M3_NUMBERS_DEF = [
    M3_SYSTEM_VOLUME,
    M3_ALARM_BELL_VOLUME,
    M3_DOORBELL_BELL_VOLUME,
    M3_ALARM_TIME_LENGTH,
    M3_DOORBELL_TIME_LENGTH,
]
