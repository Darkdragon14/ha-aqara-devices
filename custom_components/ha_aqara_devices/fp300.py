from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


FP300_BINARY_SENSORS_DEF = [
    {
        "name": "Presence",
        "key": "report_status01",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "icon": "mdi:motion-sensor",
        "on_values": {"1"},
    },
]


FP300_SENSOR_SPECS = [
    {
        "name": "Temperature",
        "key": "environment_temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "°C",
        "icon": "mdi:thermometer",
        "value_type": "float",
        "scale": 0.01,
    },
    {
        "name": "Humidity",
        "key": "environment_humidity",
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
        "icon": "mdi:water-percent",
        "value_type": "float",
        "scale": 0.01,
    },
    {
        "name": "Illuminance",
        "key": "lux",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "lx",
        "icon": "mdi:brightness-6",
        "value_type": "float",
    },
    {
        "name": "Battery",
        "key": "battery_percentage",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
        "icon": "mdi:battery",
        "value_type": "float",
    },
]
