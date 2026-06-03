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

G4_SENSORS_DEF = [
    G410_FACE_RECOGNITION_EVENT,
    G410_STRANGER_FACE_EVENT,
]

A100_PRO_DOOR_EVENT = {
    "name": "Door Event",
    "icon": "mdi:door",
    "inApp": "door_event",
    "api": "13.17.85",
    "value_type": "uint8_t",
    "value_map": {
        "0": "Door opened",
        "1": "Door closed",
        "2": "Timeout without closing",
        "3": "Knock on the door",
        "4": "Attempted break-in",
        "5": "Door ajar",
    },
    "default": None,
}

A100_PRO_LOCK_STATE = {
    "name": "Door Lock Status",
    "icon": "mdi:lock",
    "inApp": "lock_state",
    "api": "13.88.85",
    "value_type": "uint8_t",
    "value_map": {
        "1": "Door can't be closed",
        "2": "Door is open",
        "3": "Door is closed but front handle is not lifted",
        "4": "Door is locked",
        "5": "Door is locked by night latch knob",
        "6": "Door is unlocked",
        "7": "Door is locked by front handle and night latch knob",
        "8": "Door is almost closed",
    },
    "default": None,
}

A100_PRO_OPEN_DOOR_METHOD = {
    "name": "Open Door Method",
    "icon": "mdi:key-chain",
    "inApp": "open_door_method_id",
    "api": "13.18.85",
    "value_type": "uint32_t",
    "value_map": {
        "0": "Fingerprint unlock",
        "1": "Permanent password unlock",
        "2": "NFC unlock",
        "3": "Bluetooth unlock",
        "4": "Temporary password unlock",
        "5": "Mechanical key unlock",
        "6": "Dual authentication unlock",
        "7": "Duress fingerprint unlock",
        "8": "HomeKit unlock",
        "9": "Face unlock",
        "10": "AIoT remote unlock",
        "11": "Google password unlock",
        "15": "Outdoor unlock",
    },
    "default": None,
}

A100_PRO_USER_ID_FINGERPRINT = {
    "name": "Fingerprint User ID",
    "icon": "mdi:fingerprint",
    "inApp": "user_id_fingerprint",
    "api": "13.42.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_PASSWORD = {
    "name": "Password User ID",
    "icon": "mdi:form-textbox-password",
    "inApp": "user_id_password",
    "api": "13.43.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_NFC = {
    "name": "NFC User ID",
    "icon": "mdi:nfc",
    "inApp": "user_id_nfc",
    "api": "13.44.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_BLE_HOMEKIT = {
    "name": "HomeKit Bluetooth User ID",
    "icon": "mdi:bluetooth",
    "inApp": "user_id_ble_homekit",
    "api": "13.45.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_TEMPORARY_PASSWORD = {
    "name": "Temporary Password User ID",
    "icon": "mdi:lock-clock",
    "inApp": "user_id_temporary_password",
    "api": "13.46.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_SENSORS_DEF = [
    A100_PRO_DOOR_EVENT,
    A100_PRO_LOCK_STATE,
    A100_PRO_OPEN_DOOR_METHOD,
    A100_PRO_USER_ID_FINGERPRINT,
    A100_PRO_USER_ID_PASSWORD,
    A100_PRO_USER_ID_NFC,
    A100_PRO_USER_ID_BLE_HOMEKIT,
    A100_PRO_USER_ID_TEMPORARY_PASSWORD,
]
