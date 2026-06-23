from homeassistant.const import UnitOfTemperature, PERCENTAGE

M3_TEMPERATURE = {
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
    "translation_key": "gateway_time_zone",
    "icon": "mdi:map-clock",
    "inApp": "gw_time_zone",
    "api": "14.12.85",
    "value_type": "string",
    "default": None,
}

M100_NIGHT_LIGHT_CONFIGURATION = {
    "name": "Night Light Configuration",
    "translation_key": "night_light_configuration",
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
    "translation_key": "face_recognition_event",
    "icon": "mdi:face-recognition",
    "inApp": "detect_face_event",
    "api": "13.95.85",
    "value_type": "string",
    "default": None,
}

G410_STRANGER_FACE_EVENT = {
    "name": "Stranger Face Event",
    "translation_key": "stranger_face_event",
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
    "translation_key": "door_event",
    "icon": "mdi:door",
    "inApp": "door_event",
    "api": "13.17.85",
    "value_type": "uint8_t",
    "device_class": "enum",
    "value_map": {
        "0": "door_opened",
        "1": "door_closed",
        "2": "timeout_without_closing",
        "3": "knock_on_the_door",
        "4": "attempted_break_in",
        "5": "door_ajar",
    },
    "options": [
        "door_opened",
        "door_closed",
        "timeout_without_closing",
        "knock_on_the_door",
        "attempted_break_in",
        "door_ajar",
    ],
    "default": None,
}

A100_PRO_LOCK_STATE = {
    "name": "Door Lock Status",
    "translation_key": "lock_state",
    "icon": "mdi:lock",
    "inApp": "lock_state",
    "api": "13.88.85",
    "value_type": "uint8_t",
    "device_class": "enum",
    "value_map": {
        "1": "door_cannot_be_closed",
        "2": "door_is_open",
        "3": "door_closed_handle_not_lifted",
        "4": "door_is_locked",
        "5": "door_is_locked_by_night_latch_knob",
        "6": "door_is_unlocked",
        "7": "door_is_locked_by_front_handle_and_night_latch_knob",
        "8": "door_is_almost_closed",
    },
    "options": [
        "door_cannot_be_closed",
        "door_is_open",
        "door_closed_handle_not_lifted",
        "door_is_locked",
        "door_is_locked_by_night_latch_knob",
        "door_is_unlocked",
        "door_is_locked_by_front_handle_and_night_latch_knob",
        "door_is_almost_closed",
    ],
    "default": None,
}

A100_PRO_OPEN_DOOR_METHOD = {
    "name": "Open Door Method",
    "translation_key": "open_door_method",
    "icon": "mdi:key-chain",
    "inApp": "open_door_method_id",
    "api": "13.18.85",
    "value_type": "uint32_t",
    "device_class": "enum",
    "value_map": {
        "0": "fingerprint_unlock",
        "1": "permanent_password_unlock",
        "2": "nfc_unlock",
        "3": "bluetooth_unlock",
        "4": "temporary_password_unlock",
        "5": "mechanical_key_unlock",
        "6": "dual_authentication_unlock",
        "7": "duress_fingerprint_unlock",
        "8": "homekit_unlock",
        "9": "face_unlock",
        "10": "aiot_remote_unlock",
        "11": "google_password_unlock",
        "15": "outdoor_unlock",
    },
    "options": [
        "fingerprint_unlock",
        "permanent_password_unlock",
        "nfc_unlock",
        "bluetooth_unlock",
        "temporary_password_unlock",
        "mechanical_key_unlock",
        "dual_authentication_unlock",
        "duress_fingerprint_unlock",
        "homekit_unlock",
        "face_unlock",
        "aiot_remote_unlock",
        "google_password_unlock",
        "outdoor_unlock",
    ],
    "default": None,
}

A100_PRO_USER_ID_FINGERPRINT = {
    "name": "Fingerprint User ID",
    "translation_key": "user_id_fingerprint",
    "icon": "mdi:fingerprint",
    "inApp": "user_id_fingerprint",
    "api": "13.42.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_PASSWORD = {
    "name": "Password User ID",
    "translation_key": "user_id_password",
    "icon": "mdi:form-textbox-password",
    "inApp": "user_id_password",
    "api": "13.43.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_NFC = {
    "name": "NFC User ID",
    "translation_key": "user_id_nfc",
    "icon": "mdi:nfc",
    "inApp": "user_id_nfc",
    "api": "13.44.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_BLE_HOMEKIT = {
    "name": "HomeKit Bluetooth User ID",
    "translation_key": "user_id_ble_homekit",
    "icon": "mdi:bluetooth",
    "inApp": "user_id_ble_homekit",
    "api": "13.45.85",
    "value_type": "uint32_t",
    "default": None,
}

A100_PRO_USER_ID_TEMPORARY_PASSWORD = {
    "name": "Temporary Password User ID",
    "translation_key": "user_id_temporary_password",
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

ACN002_BATTERY_LEVEL = {
    "name": "Battery Level",
    "icon": "mdi:battery",
    "inApp": "battery_level",
    "api": "3.19.85",
    "value_type": "float",
    "device_class": "battery",
    "state_class": "measurement",
    "unit": PERCENTAGE,
    "default": None,
}

ACN002_LOCK_EXCEPTION = {
    "name": "Lock Exception Alert",
    "icon": "mdi:lock-alert",
    "inApp": "lock_exception_alert",
    "api": "13.32.85",
    "value_type": "uint32_t",
    "default": None,
}

ACN002_DEVICE_ONLINE_STATUS = {
    "name": "Device Online Status",
    "icon": "mdi:lan-connect",
    "inApp": "device_online_status",
    "api": "8.0.2045",
    "value_type": "uint8_t",
    "device_class": "enum",
    "value_map": {
        "0": "offline",
        "1": "online",
    },
    "options": [
        "offline",
        "online",
    ],
    "default": None,
}

ACN002_ZIGBEE_SIGNAL_STRENGTH = {
    "name": "Zigbee Signal Strength",
    "icon": "mdi:signal",
    "inApp": "zigbee_signal_strength",
    "api": "8.0.2007",
    "value_type": "uint8_t",
    "state_class": "measurement",
    "default": None,
}

ACN002_SENSORS_DEF = [
    A100_PRO_DOOR_EVENT,
    A100_PRO_LOCK_STATE,
    A100_PRO_OPEN_DOOR_METHOD,
    ACN002_BATTERY_LEVEL,
    ACN002_LOCK_EXCEPTION,
    ACN002_DEVICE_ONLINE_STATUS,
    ACN002_ZIGBEE_SIGNAL_STRENGTH,
]
