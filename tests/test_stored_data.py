"""Tests for the DailyUsageStoredData persistence."""

import sys

import pytest

from custom_components.tankfill.sensor import DailyUsageStoredData

SensorExtraStoredData = sys.modules["homeassistant.components.sensor"].SensorExtraStoredData


def _make_super_data():
    """Create a base SensorExtraStoredData."""
    return SensorExtraStoredData(native_value=5.0, native_unit_of_measurement="L")


class TestDailyUsageStoredData:
    """Test round-tripping stored data through as_dict/from_dict."""

    def test_round_trip(self):
        data = DailyUsageStoredData(
            super_data=_make_super_data(),
            daily_usage=12.5,
            last_volume=450.0,
            last_reset="2025-01-15T10:30:00+00:00",
        )
        d = data.as_dict()
        restored = DailyUsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.daily_usage == 12.5
        assert restored.last_volume == 450.0
        assert restored.last_reset == "2025-01-15T10:30:00+00:00"

    def test_round_trip_with_none_last_volume(self):
        data = DailyUsageStoredData(
            super_data=_make_super_data(),
            daily_usage=0.0,
            last_volume=None,
            last_reset="2025-01-15T00:00:00+00:00",
        )
        d = data.as_dict()
        restored = DailyUsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.daily_usage == 0.0
        assert restored.last_volume is None

    def test_from_dict_defaults(self):
        d = _make_super_data().as_dict()
        restored = DailyUsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.daily_usage == 0.0
        assert restored.last_volume is None
        assert restored.last_reset == ""

    def test_from_dict_returns_none_for_bad_base(self):
        result = DailyUsageStoredData.from_dict({})
        assert result is None

    def test_as_dict_includes_custom_fields(self):
        data = DailyUsageStoredData(
            super_data=_make_super_data(),
            daily_usage=7.3,
            last_volume=320.0,
            last_reset="2025-06-01T00:00:00",
        )
        d = data.as_dict()

        assert "daily_usage" in d
        assert "last_volume" in d
        assert "last_reset" in d
        assert d["daily_usage"] == 7.3
        assert d["last_volume"] == 320.0
