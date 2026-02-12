"""Tests for the Tank Fill volume calculation functions."""

import math

import pytest

from custom_components.tankfill.calc import (
    calculate_volume,
    max_volume,
    segment_volume,
)

# Test tank: 100cm diameter, 200cm length
# Max volume = pi * 50^2 * 200 / 1000 = 1570.796... litres
DIAMETER = 100
LENGTH = 200
MAX_VOL = math.pi * 50**2 * 200 / 1000


class TestMaxVolume:
    """Tests for max_volume()."""

    def test_basic(self):
        assert max_volume(DIAMETER, LENGTH) == pytest.approx(MAX_VOL)

    def test_small_tank(self):
        # 50cm diameter, 100cm length
        expected = math.pi * 25**2 * 100 / 1000
        assert max_volume(50, 100) == pytest.approx(expected)


class TestSegmentVolume:
    """Tests for segment_volume() - liquid depth measured from the bottom."""

    def test_empty(self):
        assert segment_volume(0, DIAMETER, LENGTH) == 0.0

    def test_negative_depth(self):
        assert segment_volume(-5, DIAMETER, LENGTH) == 0.0

    def test_full(self):
        assert segment_volume(DIAMETER, DIAMETER, LENGTH) == pytest.approx(MAX_VOL)

    def test_overfull(self):
        assert segment_volume(DIAMETER + 10, DIAMETER, LENGTH) == pytest.approx(
            MAX_VOL
        )

    def test_half_full(self):
        # Half full = half the max volume
        assert segment_volume(50, DIAMETER, LENGTH) == pytest.approx(MAX_VOL / 2)

    def test_quarter_depth(self):
        # 25cm depth in 100cm diameter tank - should be less than half
        vol = segment_volume(25, DIAMETER, LENGTH)
        assert 0 < vol < MAX_VOL / 2

    def test_three_quarter_depth(self):
        # 75cm depth - should be more than half
        vol = segment_volume(75, DIAMETER, LENGTH)
        assert MAX_VOL / 2 < vol < MAX_VOL

    def test_symmetry(self):
        # Volume at depth d + volume at depth (diameter - d) should equal max
        vol_low = segment_volume(20, DIAMETER, LENGTH)
        vol_high = segment_volume(80, DIAMETER, LENGTH)
        assert vol_low + vol_high == pytest.approx(MAX_VOL)

    def test_very_small_depth(self):
        vol = segment_volume(1, DIAMETER, LENGTH)
        assert 0 < vol < MAX_VOL * 0.01


class TestCalculateVolume:
    """Tests for calculate_volume() - sensor distance from the top."""

    def test_tank_full_sensor_at_zero(self):
        # Sensor distance 0 = liquid at the very top = full
        assert calculate_volume(0, DIAMETER, LENGTH) == pytest.approx(MAX_VOL)

    def test_tank_full_sensor_negative(self):
        # Negative sensor distance = still full (clamped)
        assert calculate_volume(-5, DIAMETER, LENGTH) == pytest.approx(MAX_VOL)

    def test_tank_empty_sensor_at_diameter(self):
        # Sensor distance = diameter = no liquid
        assert calculate_volume(DIAMETER, DIAMETER, LENGTH) == 0.0

    def test_tank_empty_sensor_beyond_diameter(self):
        # Sensor distance > diameter = still empty
        assert calculate_volume(DIAMETER + 10, DIAMETER, LENGTH) == 0.0

    def test_half_full(self):
        # Sensor distance = 50 = half the diameter = half full
        assert calculate_volume(50, DIAMETER, LENGTH) == pytest.approx(MAX_VOL / 2)

    def test_mostly_full(self):
        # Sensor distance 10 = liquid depth 90 = more than half full
        vol = calculate_volume(10, DIAMETER, LENGTH)
        assert MAX_VOL / 2 < vol < MAX_VOL

    def test_mostly_empty(self):
        # Sensor distance 90 = liquid depth 10 = less than half
        vol = calculate_volume(90, DIAMETER, LENGTH)
        assert 0 < vol < MAX_VOL / 2

    def test_continuity_at_half(self):
        # Values just above and below half should be close (0.02cm apart)
        vol_just_below = calculate_volume(50.01, DIAMETER, LENGTH)
        vol_just_above = calculate_volume(49.99, DIAMETER, LENGTH)
        assert abs(vol_just_above - vol_just_below) < 1.0

    def test_monotonically_decreasing(self):
        # As sensor distance increases, volume should decrease
        prev_vol = MAX_VOL
        for dist in range(1, DIAMETER + 1):
            vol = calculate_volume(dist, DIAMETER, LENGTH)
            assert vol < prev_vol, f"Volume not decreasing at distance {dist}"
            prev_vol = vol

    def test_inverse_relationship(self):
        # Volume at sensor_distance d should equal segment_volume at
        # liquid_depth (diameter - d) for all values
        for dist in range(1, DIAMETER):
            vol = calculate_volume(dist, DIAMETER, LENGTH)
            liquid_depth = DIAMETER - dist
            expected = segment_volume(liquid_depth, DIAMETER, LENGTH)
            assert vol == pytest.approx(expected, abs=0.001), (
                f"Mismatch at sensor_distance={dist}"
            )
