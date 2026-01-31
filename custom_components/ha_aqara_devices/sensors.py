from homeassistant.const import UnitOfTemperature, PERCENTAGE

M3_TEMPERATURE = {
    "name": "Temperature",
    "icon": "mdi:thermometer",
    "inApp": "temperature_value",
    "api": "temperature_value",
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
    "api": "humidity_value",
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
