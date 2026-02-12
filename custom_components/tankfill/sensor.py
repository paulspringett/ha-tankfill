"""Sensor platform for Tank Fill integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfVolume
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .calc import calculate_volume, max_volume
from .const import (
    CONF_DEPTH_SENSOR,
    CONF_PRICE_PER_LITRE,
    CONF_TANK_DIAMETER,
    CONF_TANK_LENGTH,
    DEFAULT_PRICE_PER_LITRE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tank Fill sensors from a config entry."""
    depth_sensor_id = entry.data[CONF_DEPTH_SENSOR]
    diameter = entry.data[CONF_TANK_DIAMETER]
    length = entry.data[CONF_TANK_LENGTH]
    price = entry.options.get(CONF_PRICE_PER_LITRE, DEFAULT_PRICE_PER_LITRE)

    oil_depth_sensor = TankOilDepthSensor(entry)
    volume_sensor = TankVolumeSensor(entry, diameter, length)
    percentage_sensor = TankFillPercentageSensor(entry, diameter, length)
    daily_usage_sensor = TankDailyUsageSensor(entry)
    daily_cost_sensor = TankDailyCostSensor(entry, price)

    # Wire up the daily usage -> daily cost callback
    daily_usage_sensor.set_cost_sensor(daily_cost_sensor)

    async_add_entities(
        [oil_depth_sensor, volume_sensor, percentage_sensor, daily_usage_sensor, daily_cost_sensor],
        update_before_add=False,
    )

    @callback
    def _async_sensor_changed(event: Event[EventStateChangedData]) -> None:
        """Handle depth sensor state changes."""
        new_state = event.data["new_state"]
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            depth = float(new_state.state)
        except (ValueError, TypeError):
            return

        liquid_depth = diameter - depth
        volume = calculate_volume(depth, diameter, length)
        max_vol = max_volume(diameter, length)

        oil_depth_sensor.update_depth(liquid_depth)
        volume_sensor.update_volume(volume)
        percentage_sensor.update_percentage(volume, max_vol)
        daily_usage_sensor.update_usage(volume)

    # Listen for changes on the external depth sensor
    entry.async_on_unload(
        async_track_state_change_event(hass, depth_sensor_id, _async_sensor_changed)
    )

    # Also process the current state immediately if available
    current_state = hass.states.get(depth_sensor_id)
    if (
        current_state is not None
        and current_state.state not in ("unknown", "unavailable")
    ):
        try:
            depth = float(current_state.state)
        except (ValueError, TypeError):
            pass
        else:
            liquid_depth = diameter - depth
            volume = calculate_volume(depth, diameter, length)
            max_vol = max_volume(diameter, length)
            oil_depth_sensor.update_depth(liquid_depth)
            volume_sensor.update_volume(volume)
            percentage_sensor.update_percentage(volume, max_vol)
            daily_usage_sensor.update_usage(volume)


class TankFillBaseSensor(SensorEntity):
    """Base class for Tank Fill sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the sensor."""
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Oil Tank",
            manufacturer="Tank Fill",
        )


class TankOilDepthSensor(TankFillBaseSensor):
    """Sensor for oil depth in cm."""

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfLength.CENTIMETERS
    _attr_suggested_display_precision = 1
    _attr_translation_key = "oil_depth"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the oil depth sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_oil_depth"

    @callback
    def update_depth(self, depth: float) -> None:
        """Update the oil depth value."""
        self._attr_native_value = round(max(depth, 0.0), 1)
        self.async_write_ha_state()


class TankVolumeSensor(TankFillBaseSensor):
    """Sensor for current oil volume in litres."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 0
    _attr_translation_key = "oil_volume"

    def __init__(
        self, entry: ConfigEntry, diameter: float, length: float
    ) -> None:
        """Initialise the volume sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_volume"
        self._diameter = diameter
        self._length = length

    @callback
    def update_volume(self, volume: float) -> None:
        """Update the volume value."""
        self._attr_native_value = round(volume, 1)
        self.async_write_ha_state()


class TankFillPercentageSensor(TankFillBaseSensor):
    """Sensor for tank fill percentage."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _attr_translation_key = "oil_fill_percentage"

    def __init__(
        self, entry: ConfigEntry, diameter: float, length: float
    ) -> None:
        """Initialise the percentage sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_fill_percentage"
        self._diameter = diameter
        self._length = length

    @callback
    def update_percentage(self, volume: float, max_vol: float) -> None:
        """Update the fill percentage."""
        if max_vol > 0:
            self._attr_native_value = round(volume / max_vol * 100, 1)
        else:
            self._attr_native_value = 0
        self.async_write_ha_state()


class DailyUsageStoredData(SensorExtraStoredData):
    """Stored data for the daily usage sensor."""

    def __init__(
        self,
        super_data: SensorExtraStoredData,
        daily_usage: float,
        last_volume: float | None,
        last_reset: str,
    ) -> None:
        """Initialise stored data."""
        super().__init__(
            super_data.native_value, super_data.native_unit_of_measurement
        )
        self.daily_usage = daily_usage
        self.last_volume = last_volume
        self.last_reset = last_reset

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored data."""
        data = super().as_dict()
        data["daily_usage"] = self.daily_usage
        data["last_volume"] = self.last_volume
        data["last_reset"] = self.last_reset
        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> DailyUsageStoredData | None:
        """Initialize stored data from a dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None
        return cls(
            extra,
            daily_usage=restored.get("daily_usage", 0.0),
            last_volume=restored.get("last_volume"),
            last_reset=restored.get("last_reset", ""),
        )


class TankDailyUsageSensor(TankFillBaseSensor, RestoreSensor):
    """Sensor for daily oil usage in litres."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1
    _attr_translation_key = "oil_daily_usage"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the daily usage sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_daily_usage"
        self._daily_usage: float = 0.0
        self._last_volume: float | None = None
        self._cost_sensor: TankDailyCostSensor | None = None

    def set_cost_sensor(self, cost_sensor: TankDailyCostSensor) -> None:
        """Set reference to the cost sensor for direct updates."""
        self._cost_sensor = cost_sensor

    @property
    def extra_restore_state_data(self) -> DailyUsageStoredData:
        """Return sensor-specific state data to be stored."""
        return DailyUsageStoredData(
            super().extra_restore_state_data,
            daily_usage=self._daily_usage,
            last_volume=self._last_volume,
            last_reset=dt_util.now().isoformat(),
        )

    async def async_added_to_hass(self) -> None:
        """Restore state and set up midnight reset."""
        await super().async_added_to_hass()

        if (extra_data := await self.async_get_last_extra_data()) is not None:
            last_data = DailyUsageStoredData.from_dict(extra_data.as_dict())
            if last_data is not None:
                # Check if midnight was missed while HA was down
                last_reset_str = last_data.last_reset
                if last_reset_str:
                    try:
                        last_reset_dt = datetime.fromisoformat(last_reset_str)
                        now = dt_util.now()
                        if last_reset_dt.date() < now.date():
                            # Midnight passed while HA was down - reset
                            self._daily_usage = 0.0
                            self._last_volume = None
                            self._attr_last_reset = now.replace(
                                hour=0, minute=0, second=0, microsecond=0
                            )
                        else:
                            self._daily_usage = last_data.daily_usage
                            self._last_volume = last_data.last_volume
                    except (ValueError, TypeError):
                        self._daily_usage = last_data.daily_usage
                        self._last_volume = last_data.last_volume
                else:
                    self._daily_usage = last_data.daily_usage
                    self._last_volume = last_data.last_volume

                self._attr_native_value = round(self._daily_usage, 1)

        # Set up midnight reset
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_reset, hour=0, minute=0, second=0
            )
        )

    @callback
    def _async_midnight_reset(self, now: datetime) -> None:
        """Reset daily usage at midnight."""
        self._daily_usage = 0.0
        self._last_volume = None
        self._attr_native_value = 0.0
        self._attr_last_reset = dt_util.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.async_write_ha_state()
        if self._cost_sensor is not None:
            self._cost_sensor.update_cost(0.0)

    @callback
    def update_usage(self, new_volume: float) -> None:
        """Update daily usage based on volume change."""
        if self._last_volume is not None:
            if new_volume < self._last_volume:
                # Volume decreased = consumption
                self._daily_usage += self._last_volume - new_volume
            # Volume increased = refill, ignore delta

        self._last_volume = new_volume
        self._attr_native_value = round(self._daily_usage, 1)
        self.async_write_ha_state()

        if self._cost_sensor is not None:
            self._cost_sensor.update_cost(self._daily_usage)


class TankDailyCostSensor(TankFillBaseSensor):
    """Sensor for daily oil cost in GBP."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "GBP"
    _attr_suggested_display_precision = 2
    _attr_translation_key = "oil_daily_cost"

    def __init__(self, entry: ConfigEntry, price_per_litre: float) -> None:
        """Initialise the daily cost sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_daily_cost"
        self._price_per_litre = price_per_litre
        self._attr_native_value = 0.0

    @callback
    def update_cost(self, daily_usage: float) -> None:
        """Update the cost based on daily usage."""
        self._attr_native_value = round(daily_usage * self._price_per_litre, 2)
        self.async_write_ha_state()
