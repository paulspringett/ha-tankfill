"""Tests for daily usage tracking logic."""

import pytest

from custom_components.tankfill.sensor import (
    TankDailyCostSensor,
    TankDailyUsageSensor,
)


class FakeConfigEntry:
    """Minimal config entry for testing."""

    def __init__(self, entry_id="test_entry"):
        self.entry_id = entry_id


def make_usage_sensor() -> TankDailyUsageSensor:
    """Create a TankDailyUsageSensor with async_write_ha_state stubbed."""
    sensor = TankDailyUsageSensor(FakeConfigEntry())
    sensor.async_write_ha_state = lambda: None
    return sensor


def make_cost_sensor(price: float = 0.55) -> TankDailyCostSensor:
    """Create a TankDailyCostSensor with async_write_ha_state stubbed."""
    sensor = TankDailyCostSensor(FakeConfigEntry(), price_per_litre=price)
    sensor.async_write_ha_state = lambda: None
    return sensor


class TestDailyUsageTracking:
    """Test the update_usage callback logic in isolation."""

    def test_first_reading_no_usage(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        assert sensor._daily_usage == 0.0
        assert sensor._last_volume == 500.0

    def test_consumption_accumulates(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)  # initial
        sensor.update_usage(490.0)  # consumed 10
        assert sensor._daily_usage == pytest.approx(10.0)
        sensor.update_usage(480.0)  # consumed another 10
        assert sensor._daily_usage == pytest.approx(20.0)

    def test_refill_ignored(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(490.0)  # consumed 10
        sensor.update_usage(800.0)  # refill!
        assert sensor._daily_usage == pytest.approx(10.0)

    def test_consumption_after_refill(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(490.0)  # consumed 10
        sensor.update_usage(900.0)  # refill
        sensor.update_usage(880.0)  # consumed 20 after refill
        assert sensor._daily_usage == pytest.approx(30.0)

    def test_no_change_no_usage(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(500.0)
        assert sensor._daily_usage == 0.0

    def test_native_value_rounded(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(499.666)
        assert sensor._attr_native_value == 0.3  # 0.334 rounded to 1dp

    def test_cost_sensor_called_on_usage(self):
        sensor = make_usage_sensor()
        cost = make_cost_sensor()
        sensor.set_cost_sensor(cost)

        sensor.update_usage(500.0)
        sensor.update_usage(490.0)
        assert cost._attr_native_value == pytest.approx(10.0 * 0.55)

    def test_works_without_cost_sensor(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(490.0)

    def test_small_incremental_consumption(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        for i in range(100):
            sensor.update_usage(500.0 - (i + 1) * 0.1)
        assert sensor._daily_usage == pytest.approx(10.0)


class TestMidnightReset:
    """Test the midnight reset callback."""

    def test_resets_usage(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(490.0)
        assert sensor._daily_usage == pytest.approx(10.0)

        sensor._async_midnight_reset(None)
        assert sensor._daily_usage == 0.0
        assert sensor._last_volume is None
        assert sensor._attr_native_value == 0.0

    def test_resets_cost_sensor(self):
        sensor = make_usage_sensor()
        cost = make_cost_sensor()
        sensor.set_cost_sensor(cost)

        sensor.update_usage(500.0)
        sensor.update_usage(490.0)
        sensor._async_midnight_reset(None)
        assert cost._attr_native_value == 0.0

    def test_first_reading_after_reset_no_usage(self):
        sensor = make_usage_sensor()
        sensor.update_usage(500.0)
        sensor.update_usage(490.0)
        sensor._async_midnight_reset(None)

        # First reading after reset should not count as consumption
        sensor.update_usage(488.0)
        assert sensor._daily_usage == 0.0

        # Second reading should count
        sensor.update_usage(480.0)
        assert sensor._daily_usage == pytest.approx(8.0)


class TestDailyCostSensor:
    """Test the cost sensor."""

    def test_cost_calculation(self):
        sensor = make_cost_sensor(0.55)
        sensor.update_cost(10.0)
        assert sensor._attr_native_value == 5.50

    def test_cost_rounding(self):
        sensor = make_cost_sensor(0.55)
        sensor.update_cost(3.333)
        assert sensor._attr_native_value == 1.83

    def test_zero_usage(self):
        sensor = make_cost_sensor(0.55)
        sensor.update_cost(0.0)
        assert sensor._attr_native_value == 0.0

    def test_different_price(self):
        sensor = make_cost_sensor(0.72)
        sensor.update_cost(100.0)
        assert sensor._attr_native_value == 72.0
