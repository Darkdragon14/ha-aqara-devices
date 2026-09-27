from __future__ import annotations


M1S_LIGHT_STATUS = {
    "inApp": "corridor_light_status",
    "api": "14.7.111",
    "value_type": "bool",
}

M1S_LIGHT_BRIGHTNESS = {
    "inApp": "brightness_level",
    "api": "14.7.1006",
    "value_type": "uint8_t",
}

M1S_LIGHT_ARGB = {
    "inApp": "argb_value",
    "api": "14.7.85",
    "value_type": "uint32_t",
}

M1S_LIGHT_STATE_SPECS = [
    M1S_LIGHT_STATUS,
    M1S_LIGHT_BRIGHTNESS,
    M1S_LIGHT_ARGB,
]
