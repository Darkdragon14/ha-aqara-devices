from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass


FP300_BINARY_SENSORS_DEF = [
    {
        "name": "Presence",
        "key": "report_status01",
        "api": "3.51.85",
        "poll_group": "fast",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
        "icon": "mdi:motion-sensor",
        "on_values": {"1"},
    },
]


FP300_SENSOR_SPECS = [
    {
        "name": "Temperature",
        "key": "environment_temperature",
        "api": "0.1.85",
        "poll_group": "medium",
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
        "api": "0.2.85",
        "poll_group": "medium",
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
        "api": "0.3.85",
        "poll_group": "medium",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "lx",
        "icon": "mdi:brightness-6",
        "value_type": "float",
    },
    {
        "name": "Battery",
        "key": "battery_percentage",
        "api": "8.0.2001",
        "poll_group": "slow",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": "%",
        "icon": "mdi:battery",
        "value_type": "float",
    },
]
