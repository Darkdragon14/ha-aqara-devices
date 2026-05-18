from homeassistant.const import UnitOfTemperature, PERCENTAGE

M3_TEMPERATURE = {
    "name": "Temperature",
    "icon": "mdi:thermometer",
    "inApp": "temperature_value",
    "api": "0.1.85",
    "value_type": "float",
    "scale": 0.01,
    "device_class": "temperature",
    "state_class": "measurement",
    "unit": UnitOfTemperature.CELSIUS,
    "default": None,
}

M3_HUMIDITY = {
    "name": "Humidity",
    "icon": "mdi:water-percent",
    "inApp": "humidity_value",
    "api": "0.2.85",
    "value_type": "float",
    "device_class": "humidity",
    "state_class": "measurement",
    "unit": PERCENTAGE,
    "default": None,
}

M3_SENSORS_DEF = [
    M3_TEMPERATURE,
    M3_HUMIDITY,
]

M100_GATEWAY_TIME_ZONE = {
    "name": "Gateway Time Zone",
    "icon": "mdi:map-clock",
    "inApp": "gw_time_zone",
    "api": "14.12.85",
    "value_type": "string",
    "default": None,
}

M100_NIGHT_LIGHT_CONFIGURATION = {
    "name": "Night Light Configuration",
    "icon": "mdi:weather-night",
    "inApp": "en_nnlight",
    "api": "14.21.85",
    "value_type": "int",
    "default": None,
}

M100_SENSORS_DEF = [
    M100_GATEWAY_TIME_ZONE,
    M100_NIGHT_LIGHT_CONFIGURATION,
]

G410_BATTERY_LEVEL = {
    "name": "Battery Level",
    "icon": "mdi:battery",
    "inApp": "device_battery_power",
    "api": "8.0.2001",
    "value_type": "float",
    "device_class": "battery",
    "state_class": "measurement",
    "unit": PERCENTAGE,
    "default": None,
}

G410_FACE_RECOGNITION_EVENT = {
    "name": "Face Recognition Event",
    "icon": "mdi:face-recognition",
    "inApp": "detect_face_event",
    "api": "13.95.85",
    "value_type": "string",
    "default": None,
}

G410_STRANGER_FACE_EVENT = {
    "name": "Stranger Face Event",
    "icon": "mdi:face-agent",
    "inApp": "detect_stranger_face_event",
    "api": "13.108.85",
    "value_type": "string",
    "default": None,
}

G410_SENSORS_DEF = [
    G410_BATTERY_LEVEL,
    G410_FACE_RECOGNITION_EVENT,
    G410_STRANGER_FACE_EVENT,
]
