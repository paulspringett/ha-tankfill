"""Shared test fixtures - mock Home Assistant modules."""

import sys
from unittest.mock import MagicMock

# Mock all homeassistant modules before any test imports.
# This must happen at conftest load time, before pytest collects test files.
_HA_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.event",
    "homeassistant.helpers.restore_state",
    "homeassistant.util",
    "homeassistant.util.dt",
]

for mod_name in _HA_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Set up realistic stand-ins for the HA classes our code inherits from or uses

_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorEntity = type("SensorEntity", (), {"_attr_should_poll": False})
_sensor_mod.RestoreSensor = type("RestoreSensor", (_sensor_mod.SensorEntity,), {})
_sensor_mod.SensorDeviceClass = MagicMock()
_sensor_mod.SensorStateClass = MagicMock()


class _SensorExtraStoredData:
    """Minimal stand-in for SensorExtraStoredData."""

    def __init__(self, native_value=None, native_unit_of_measurement=None):
        self.native_value = native_value
        self.native_unit_of_measurement = native_unit_of_measurement

    @property
    def extra_restore_state_data(self):
        return _SensorExtraStoredData(self.native_value, self.native_unit_of_measurement)

    def as_dict(self):
        return {
            "native_value": self.native_value,
            "native_unit_of_measurement": self.native_unit_of_measurement,
        }

    @classmethod
    def from_dict(cls, data):
        if "native_value" not in data:
            return None
        return cls(
            native_value=data.get("native_value"),
            native_unit_of_measurement=data.get("native_unit_of_measurement"),
        )


_sensor_mod.SensorExtraStoredData = _SensorExtraStoredData

# homeassistant.const
sys.modules["homeassistant.const"].UnitOfVolume = MagicMock()
sys.modules["homeassistant.const"].UnitOfVolume.LITERS = "L"
sys.modules["homeassistant.const"].Platform = MagicMock()
sys.modules["homeassistant.const"].Platform.SENSOR = "sensor"

# homeassistant.core
sys.modules["homeassistant.core"].callback = lambda f: f
sys.modules["homeassistant.core"].Event = MagicMock()
sys.modules["homeassistant.core"].EventStateChangedData = MagicMock()
sys.modules["homeassistant.core"].HomeAssistant = MagicMock()

# homeassistant.helpers
sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
