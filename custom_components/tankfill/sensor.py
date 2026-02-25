"""Sensor platform for Tank Fill integration."""

from __future__ import annotations

from datetime import datetime, timedelta
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
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .calc import calculate_volume, max_volume
from .const import (
    CONF_DEPTH_SENSOR,
    CONF_PRICE_PER_LITRE,
    CONF_PRICE_SENSOR,
    CONF_TANK_DIAMETER,
    CONF_TANK_LENGTH,
    DEFAULT_PRICE_PER_LITRE,
    DOMAIN,
)
from .usage_history import UsageHistory

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
    price_sensor_id = entry.options.get(CONF_PRICE_SENSOR) or None

    oil_depth_sensor = TankOilDepthSensor(entry)
    volume_sensor = TankVolumeSensor(entry, diameter, length)
    percentage_sensor = TankFillPercentageSensor(entry, diameter, length)

    # Usage period sensors
    weekly_usage = TankPeriodUsageSensor(entry, "weekly_usage", "oil_weekly_usage")
    monthly_usage = TankPeriodUsageSensor(entry, "monthly_usage", "oil_monthly_usage")
    yearly_usage = TankPeriodUsageSensor(entry, "yearly_usage", "oil_yearly_usage")

    # Cost sensors
    daily_cost = TankPeriodCostSensor(entry, "daily_cost", "oil_avg_daily_cost", price)
    weekly_cost = TankPeriodCostSensor(entry, "weekly_cost", "oil_weekly_cost", price)
    monthly_cost = TankPeriodCostSensor(entry, "monthly_cost", "oil_monthly_cost", price)
    yearly_cost = TankPeriodCostSensor(entry, "yearly_cost", "oil_yearly_cost", price)

    # Refill sensor
    last_refill_sensor = TankLastRefillSensor(entry)

    # Tracker sensor (avg daily usage) — owns UsageHistory and drives all dependents
    tracker = TankUsageTrackerSensor(
        entry,
        usage_sensors={"weekly": weekly_usage, "monthly": monthly_usage, "yearly": yearly_usage},
        cost_sensors={
            "daily": daily_cost,
            "weekly": weekly_cost,
            "monthly": monthly_cost,
            "yearly": yearly_cost,
        },
        refill_sensor=last_refill_sensor,
        price_sensor_id=price_sensor_id,
    )

    async_add_entities(
        [
            oil_depth_sensor,
            volume_sensor,
            percentage_sensor,
            tracker,
            weekly_usage,
            monthly_usage,
            yearly_usage,
            daily_cost,
            weekly_cost,
            monthly_cost,
            yearly_cost,
            last_refill_sensor,
        ],
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
        tracker.update_usage(volume)

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
            tracker.update_usage(volume)


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


class TankLastRefillSensor(TankFillBaseSensor):
    """Sensor showing the date/time of the last tank refill."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "oil_last_refill"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise the last refill sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_last_refill"

    @callback
    def set_refill(self, refill_info: dict) -> None:
        """Update from a refill detection dict."""
        self._attr_native_value = datetime.fromisoformat(refill_info["timestamp"])
        self._attr_extra_state_attributes = {
            "volume_before": refill_info["volume_before"],
            "volume_after": refill_info["volume_after"],
            "litres_added": refill_info["litres_added"],
        }
        self.async_write_ha_state()


class UsageStoredData(SensorExtraStoredData):
    """Stored data for the usage tracker sensor."""

    def __init__(
        self,
        super_data: SensorExtraStoredData,
        readings: list[dict[str, str | float]],
        last_refill: dict | None = None,
        sensor_price: float | None = None,
    ) -> None:
        """Initialise stored data."""
        super().__init__(
            super_data.native_value, super_data.native_unit_of_measurement
        )
        self.readings = readings
        self.last_refill = last_refill
        self.sensor_price = sensor_price

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the stored data."""
        data = super().as_dict()
        data["readings"] = self.readings
        data["last_refill"] = self.last_refill
        data["sensor_price"] = self.sensor_price
        return data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> UsageStoredData | None:
        """Initialize stored data from a dict."""
        extra = SensorExtraStoredData.from_dict(restored)
        if extra is None:
            return None
        return cls(
            extra,
            readings=restored.get("readings", []),
            last_refill=restored.get("last_refill"),
            sensor_price=restored.get("sensor_price"),
        )


class TankUsageTrackerSensor(TankFillBaseSensor, RestoreSensor):
    """Sensor for average daily oil usage (weekly_usage / 7).

    Owns the UsageHistory and pushes values to dependent usage and cost sensors.
    """

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1
    _attr_translation_key = "oil_avg_daily_usage"

    def __init__(
        self,
        entry: ConfigEntry,
        usage_sensors: dict[str, TankPeriodUsageSensor],
        cost_sensors: dict[str, TankPeriodCostSensor],
        refill_sensor: TankLastRefillSensor | None = None,
        price_sensor_id: str | None = None,
    ) -> None:
        """Initialise the usage tracker sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_daily_usage"
        self._history = UsageHistory()
        self._usage_sensors = usage_sensors
        self._cost_sensors = cost_sensors
        self._refill_sensor = refill_sensor
        self._price_sensor_id = price_sensor_id
        self._sensor_price: float | None = None
        self._last_refill: dict | None = None

    @property
    def extra_restore_state_data(self) -> UsageStoredData:
        """Return sensor-specific state data to be stored."""
        return UsageStoredData(
            super().extra_restore_state_data,
            readings=self._history.as_list(),
            last_refill=self._last_refill,
            sensor_price=self._sensor_price,
        )

    async def async_added_to_hass(self) -> None:
        """Restore usage history from stored data."""
        await super().async_added_to_hass()

        if (extra_data := await self.async_get_last_extra_data()) is not None:
            last_data = UsageStoredData.from_dict(extra_data.as_dict())
            if last_data is not None and last_data.readings:
                self._history = UsageHistory.from_list(last_data.readings)
                self._recalculate()
            if last_data is not None and last_data.last_refill:
                self._last_refill = last_data.last_refill
                if self._refill_sensor is not None:
                    self._refill_sensor.set_refill(self._last_refill)
            if (
                last_data is not None
                and last_data.sensor_price is not None
                and self._price_sensor_id is not None
            ):
                self._sensor_price = last_data.sensor_price
                for cost_sensor in self._cost_sensors.values():
                    cost_sensor.update_price(self._sensor_price)

    @callback
    def update_usage(self, volume: float) -> None:
        """Record a new volume reading and recalculate all sensors."""
        refill = self._history.add_reading(dt_util.now(), volume)
        if refill is not None:
            self._last_refill = refill
            if self._refill_sensor is not None:
                self._refill_sensor.set_refill(refill)
            if self._price_sensor_id is not None:
                self._capture_price_from_sensor()
        self._recalculate()

    def _capture_price_from_sensor(self) -> None:
        """Read the price sensor and update cost sensors if valid."""
        state = self.hass.states.get(self._price_sensor_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return
        try:
            price = float(state.state)
        except (ValueError, TypeError):
            return
        self._sensor_price = price
        for cost_sensor in self._cost_sensors.values():
            cost_sensor.update_price(price)

    def _recalculate(self) -> None:
        """Recalculate all rolling-window values and push to dependents."""
        now = dt_util.now()
        weekly = self._history.usage_since(now - timedelta(days=7))
        monthly = self._history.usage_since(now - timedelta(days=30))
        yearly = self._history.usage_since(now - timedelta(days=365))
        avg_daily = weekly / 7

        # Own value: avg daily usage
        self._attr_native_value = round(avg_daily, 1)
        self.async_write_ha_state()

        # Push to usage sensors
        self._usage_sensors["weekly"].set_value(weekly)
        self._usage_sensors["monthly"].set_value(monthly)
        self._usage_sensors["yearly"].set_value(yearly)

        # Push to cost sensors
        self._cost_sensors["daily"].set_value(avg_daily)
        self._cost_sensors["weekly"].set_value(weekly)
        self._cost_sensors["monthly"].set_value(monthly)
        self._cost_sensors["yearly"].set_value(yearly)


class TankPeriodUsageSensor(TankFillBaseSensor):
    """Sensor for usage over a rolling period (weekly/monthly/yearly)."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 1

    def __init__(
        self, entry: ConfigEntry, id_suffix: str, translation_key: str
    ) -> None:
        """Initialise a period usage sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_{id_suffix}"
        self._attr_translation_key = translation_key

    @callback
    def set_value(self, usage: float) -> None:
        """Update the usage value."""
        self._attr_native_value = round(usage, 1)
        self.async_write_ha_state()


class TankPeriodCostSensor(TankFillBaseSensor):
    """Sensor for cost over a rolling period."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "GBP"
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        entry: ConfigEntry,
        id_suffix: str,
        translation_key: str,
        price_per_litre: float,
    ) -> None:
        """Initialise a period cost sensor."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_{id_suffix}"
        self._attr_translation_key = translation_key
        self._price_per_litre = price_per_litre

    def update_price(self, new_price: float) -> None:
        """Update the price per litre used for cost calculations."""
        self._price_per_litre = new_price

    @callback
    def set_value(self, usage: float) -> None:
        """Update the cost value based on usage."""
        self._attr_native_value = round(usage * self._price_per_litre, 2)
        self.async_write_ha_state()
