"""Tests for the rolling-window usage and cost sensors."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.tankfill.sensor import (
    TankLastRefillSensor,
    TankPeriodCostSensor,
    TankPeriodUsageSensor,
    TankUsageTrackerSensor,
)


class FakeConfigEntry:
    """Minimal config entry for testing."""

    def __init__(self, entry_id="test_entry"):
        self.entry_id = entry_id


def _stub_write(sensor):
    """Stub async_write_ha_state on a sensor."""
    sensor.async_write_ha_state = lambda: None


def _make_sensors(price: float = 0.55, price_sensor_id: str | None = None):
    """Create a full set of tracker + period + cost + refill sensors for testing."""
    entry = FakeConfigEntry()

    weekly = TankPeriodUsageSensor(entry, "weekly_usage", "oil_weekly_usage")
    monthly = TankPeriodUsageSensor(entry, "monthly_usage", "oil_monthly_usage")
    yearly = TankPeriodUsageSensor(entry, "yearly_usage", "oil_yearly_usage")

    daily_cost = TankPeriodCostSensor(entry, "daily_cost", "oil_avg_daily_cost", price)
    weekly_cost = TankPeriodCostSensor(entry, "weekly_cost", "oil_weekly_cost", price)
    monthly_cost = TankPeriodCostSensor(entry, "monthly_cost", "oil_monthly_cost", price)
    yearly_cost = TankPeriodCostSensor(entry, "yearly_cost", "oil_yearly_cost", price)

    refill = TankLastRefillSensor(entry)

    tracker = TankUsageTrackerSensor(
        entry,
        usage_sensors={"weekly": weekly, "monthly": monthly, "yearly": yearly},
        cost_sensors={
            "daily": daily_cost,
            "weekly": weekly_cost,
            "monthly": monthly_cost,
            "yearly": yearly_cost,
        },
        refill_sensor=refill,
        price_sensor_id=price_sensor_id,
    )

    # Stub async_write_ha_state on all sensors
    for s in [tracker, weekly, monthly, yearly, daily_cost, weekly_cost, monthly_cost, yearly_cost, refill]:
        _stub_write(s)

    return tracker, {
        "weekly": weekly,
        "monthly": monthly,
        "yearly": yearly,
        "daily_cost": daily_cost,
        "weekly_cost": weekly_cost,
        "monthly_cost": monthly_cost,
        "yearly_cost": yearly_cost,
        "refill": refill,
    }


def _fake_now(days_ago: float = 0):
    """Return a fixed datetime offset by days_ago."""
    base = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return base - timedelta(days=days_ago)


class TestTrackerSensor:
    """Test the TankUsageTrackerSensor update_usage callback."""

    def test_first_reading_no_usage(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(500.0)
        assert tracker._attr_native_value == 0.0

    def test_consumption_tracked(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(490.0)

        # Weekly usage = 10, avg daily = 10/7 ≈ 1.4
        assert sensors["weekly"]._attr_native_value == pytest.approx(10.0)
        assert tracker._attr_native_value == pytest.approx(10.0 / 7, abs=0.1)

    def test_refill_ignored(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=2)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(490.0)  # consumed 10
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(800.0)  # refill
        assert sensors["weekly"]._attr_native_value == pytest.approx(10.0)

    def test_consumption_after_refill(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=3)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now(days_ago=2)
            tracker.update_usage(490.0)  # consumed 10
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(900.0)  # refill
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(880.0)  # consumed 20
        assert sensors["weekly"]._attr_native_value == pytest.approx(30.0)

    def test_all_usage_periods_populated(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(480.0)  # consumed 20

        assert sensors["weekly"]._attr_native_value == pytest.approx(20.0)
        assert sensors["monthly"]._attr_native_value == pytest.approx(20.0)
        assert sensors["yearly"]._attr_native_value == pytest.approx(20.0)

    def test_readings_outside_weekly_window(self):
        """Readings older than 7 days should not count in weekly usage."""
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            # Old consumption (outside weekly, inside monthly)
            mock_dt.now.return_value = _fake_now(days_ago=20)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now(days_ago=15)
            tracker.update_usage(480.0)  # consumed 20
            # Recent consumption (inside weekly)
            mock_dt.now.return_value = _fake_now(days_ago=2)
            tracker.update_usage(480.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(470.0)  # consumed 10

        assert sensors["weekly"]._attr_native_value == pytest.approx(10.0)
        assert sensors["monthly"]._attr_native_value == pytest.approx(30.0)


class TestCostSensors:
    """Test cost calculations across all periods."""

    def test_cost_from_usage(self):
        price = 0.55
        tracker, sensors = _make_sensors(price=price)
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(480.0)  # consumed 20

        assert sensors["weekly_cost"]._attr_native_value == pytest.approx(20.0 * price)
        assert sensors["monthly_cost"]._attr_native_value == pytest.approx(20.0 * price)
        assert sensors["yearly_cost"]._attr_native_value == pytest.approx(20.0 * price)
        # avg daily cost = (20/7) * price
        expected_daily_cost = round(20.0 / 7 * price, 2)
        assert sensors["daily_cost"]._attr_native_value == pytest.approx(expected_daily_cost)

    def test_different_price(self):
        price = 0.72
        tracker, sensors = _make_sensors(price=price)
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(400.0)  # consumed 100

        assert sensors["weekly_cost"]._attr_native_value == pytest.approx(72.0)

    def test_zero_usage_zero_cost(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(500.0)

        assert sensors["weekly_cost"]._attr_native_value == pytest.approx(0.0)
        assert sensors["daily_cost"]._attr_native_value == pytest.approx(0.0)


class TestPeriodUsageSensor:
    """Test TankPeriodUsageSensor directly."""

    def test_set_value(self):
        sensor = TankPeriodUsageSensor(FakeConfigEntry(), "weekly_usage", "oil_weekly_usage")
        _stub_write(sensor)
        sensor.set_value(42.7)
        assert sensor._attr_native_value == 42.7

    def test_unique_id(self):
        sensor = TankPeriodUsageSensor(FakeConfigEntry(), "monthly_usage", "oil_monthly_usage")
        assert sensor._attr_unique_id == "test_entry_monthly_usage"


class TestPeriodCostSensor:
    """Test TankPeriodCostSensor directly."""

    def test_cost_calculation(self):
        sensor = TankPeriodCostSensor(FakeConfigEntry(), "weekly_cost", "oil_weekly_cost", 0.55)
        _stub_write(sensor)
        sensor.set_value(10.0)
        assert sensor._attr_native_value == 5.50

    def test_cost_rounding(self):
        sensor = TankPeriodCostSensor(FakeConfigEntry(), "daily_cost", "oil_avg_daily_cost", 0.55)
        _stub_write(sensor)
        sensor.set_value(3.333)
        assert sensor._attr_native_value == 1.83

    def test_unique_id(self):
        sensor = TankPeriodCostSensor(FakeConfigEntry(), "yearly_cost", "oil_yearly_cost", 0.55)
        assert sensor._attr_unique_id == "test_entry_yearly_cost"


class TestRefillSensor:
    """Test that the tracker detects refills and pushes to the refill sensor."""

    def test_refill_detected(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # +200L refill

        refill = sensors["refill"]
        assert refill._attr_native_value == _fake_now()
        assert refill._attr_extra_state_attributes["volume_before"] == 400.0
        assert refill._attr_extra_state_attributes["volume_after"] == 600.0
        assert refill._attr_extra_state_attributes["litres_added"] == 200.0

    def test_no_refill_for_small_increase(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(550.0)  # +50L, below threshold

        assert getattr(sensors["refill"], "_attr_native_value", None) is None

    def test_no_refill_for_consumption(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(490.0)  # consumption

        assert getattr(sensors["refill"], "_attr_native_value", None) is None

    def test_refill_sensor_unique_id(self):
        sensor = TankLastRefillSensor(FakeConfigEntry())
        assert sensor._attr_unique_id == "test_entry_last_refill"

    def test_tracker_stores_last_refill(self):
        tracker, sensors = _make_sensors()
        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)

        assert tracker._last_refill is not None
        assert tracker._last_refill["litres_added"] == 200.0


def _make_fake_hass(price_state="0.72"):
    """Create a mock hass object with a price sensor state."""
    hass = MagicMock()
    state = MagicMock()
    state.state = price_state
    hass.states.get.return_value = state
    return hass


class TestPriceSensorCapture:
    """Test that refill events capture price from a configured price sensor."""

    def test_refill_with_price_sensor_updates_cost_sensors(self):
        tracker, sensors = _make_sensors(price=0.55, price_sensor_id="sensor.oil_price")
        tracker.hass = _make_fake_hass("0.72")

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # refill

        assert tracker._sensor_price == 0.72
        for key in ("daily", "weekly", "monthly", "yearly"):
            assert sensors[f"{key}_cost"]._price_per_litre == 0.72

    def test_refill_without_price_sensor_leaves_cost_sensors_unchanged(self):
        tracker, sensors = _make_sensors(price=0.55)

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # refill

        assert tracker._sensor_price is None
        for key in ("daily", "weekly", "monthly", "yearly"):
            assert sensors[f"{key}_cost"]._price_per_litre == 0.55

    def test_non_refill_does_not_update_price(self):
        tracker, sensors = _make_sensors(price=0.55, price_sensor_id="sensor.oil_price")
        tracker.hass = _make_fake_hass("0.72")

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(500.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(490.0)  # consumption, not refill

        assert tracker._sensor_price is None
        for key in ("daily", "weekly", "monthly", "yearly"):
            assert sensors[f"{key}_cost"]._price_per_litre == 0.55

    def test_refill_with_invalid_price_sensor_state(self):
        tracker, sensors = _make_sensors(price=0.55, price_sensor_id="sensor.oil_price")
        tracker.hass = _make_fake_hass("unavailable")
        # The state itself is "unavailable"
        state = MagicMock()
        state.state = "unavailable"
        tracker.hass.states.get.return_value = state

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # refill

        assert tracker._sensor_price is None
        for key in ("daily", "weekly", "monthly", "yearly"):
            assert sensors[f"{key}_cost"]._price_per_litre == 0.55

    def test_refill_with_missing_price_sensor(self):
        tracker, sensors = _make_sensors(price=0.55, price_sensor_id="sensor.oil_price")
        tracker.hass = MagicMock()
        tracker.hass.states.get.return_value = None

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # refill

        assert tracker._sensor_price is None
        for key in ("daily", "weekly", "monthly", "yearly"):
            assert sensors[f"{key}_cost"]._price_per_litre == 0.55

    def test_sensor_price_stored_on_tracker(self):
        """Verify the tracker stores sensor_price so it can be persisted."""
        tracker, sensors = _make_sensors(price=0.55, price_sensor_id="sensor.oil_price")
        tracker.hass = _make_fake_hass("0.68")

        with patch("custom_components.tankfill.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = _fake_now(days_ago=1)
            tracker.update_usage(400.0)
            mock_dt.now.return_value = _fake_now()
            tracker.update_usage(600.0)  # refill

        assert tracker._sensor_price == 0.68
