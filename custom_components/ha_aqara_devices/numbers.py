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

M100_MUSIC_VOLUME = {
    "name": "Music Volume",
    "icon": "mdi:music-note",
    "inApp": "music_volume",
    "api": "14.3.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

M100_SYSTEM_VOLUME = {
    "name": "System Volume",
    "icon": "mdi:volume-high",
    "inApp": "system_volume",
    "api": "14.11.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

M100_CLOCK_VOLUME = {
    "name": "Alarm Clock Volume",
    "icon": "mdi:alarm",
    "inApp": "clock_volume",
    "api": "14.5.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

M100_ALARM_BELL_VOLUME = {
    "name": "Alarm Volume",
    "icon": "mdi:bell-ring",
    "inApp": "alarm_bell_volume",
    "api": "14.1.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

M100_NIGHT_LIGHT_BRIGHTNESS = {
    "name": "Night Light Brightness",
    "icon": "mdi:brightness-6",
    "inApp": "brightness_level",
    "api": "14.7.1006",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

M100_ARMING_DELAY_TIME = {
    "name": "Arming Delay Time",
    "icon": "mdi:timer-sand",
    "inApp": "arming_delay_time",
    "api": "14.6.113",
    "min": 0,
    "max": 255,
    "step": 1,
    "type": "integer",
}

M100_NUMBERS_DEF = [
    M100_MUSIC_VOLUME,
    M100_SYSTEM_VOLUME,
    M100_CLOCK_VOLUME,
    M100_ALARM_BELL_VOLUME,
    M100_NIGHT_LIGHT_BRIGHTNESS,
    M100_ARMING_DELAY_TIME,
]

G2H_PRO_MUSIC_VOLUME = {
    "name": "Music Volume",
    "icon": "mdi:music-note",
    "inApp": "music_volume",
    "api": "14.3.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G2H_PRO_CAMERA_VOLUME = {
    "name": "Camera Volume",
    "icon": "mdi:volume-high",
    "inApp": "camera_volume",
    "api": "14.65.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G2H_PRO_ALARM_BELL_VOLUME = {
    "name": "Alarm Volume",
    "icon": "mdi:bell-ring",
    "inApp": "alarm_bell_volume",
    "api": "14.1.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G2H_PRO_NUMBERS_DEF = [
    G2H_PRO_MUSIC_VOLUME,
    G2H_PRO_CAMERA_VOLUME,
    G2H_PRO_ALARM_BELL_VOLUME,
]

G410_SYSTEM_VOLUME = {
    "name": "System Volume",
    "icon": "mdi:volume-high",
    "inApp": "system_volume",
    "api": "14.11.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G410_FACE_INTERVAL = {
    "name": "Face Recognition Interval",
    "icon": "mdi:face-recognition",
    "inApp": "face_interval",
    "api": "14.110.85",
    "min": 0,
    "max": 3600,
    "step": 1,
    "type": "integer",
}

G410_ALARM_BELL_VOLUME = {
    "name": "Alarm Volume",
    "icon": "mdi:bell-ring",
    "inApp": "alarm_bell_volume",
    "api": "14.1.1000",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G410_CAMERA_VOLUME = {
    "name": "Camera Volume",
    "icon": "mdi:volume-high",
    "inApp": "camera_volume",
    "api": "14.65.85",
    "min": 0,
    "max": 100,
    "step": 1,
    "type": "integer",
}

G410_NUMBERS_DEF = [
    G410_SYSTEM_VOLUME,
    G410_FACE_INTERVAL,
    G410_ALARM_BELL_VOLUME,
    G410_CAMERA_VOLUME,
]

G4_NUMBERS_DEF = [
    G410_FACE_INTERVAL,
    G410_CAMERA_VOLUME,
]
