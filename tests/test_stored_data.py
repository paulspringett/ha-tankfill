"""Tests for the UsageStoredData persistence."""

import sys

import pytest

from custom_components.tankfill.sensor import UsageStoredData

SensorExtraStoredData = sys.modules["homeassistant.components.sensor"].SensorExtraStoredData


def _make_super_data():
    """Create a base SensorExtraStoredData."""
    return SensorExtraStoredData(native_value=5.0, native_unit_of_measurement="L")


class TestUsageStoredData:
    """Test round-tripping stored data through as_dict/from_dict."""

    def test_round_trip(self):
        readings = [
            {"t": "2025-06-14T12:00:00+00:00", "v": 500.0},
            {"t": "2025-06-15T12:00:00+00:00", "v": 490.0},
        ]
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=readings,
        )
        d = data.as_dict()
        restored = UsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.readings == readings

    def test_round_trip_empty_readings(self):
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=[],
        )
        d = data.as_dict()
        restored = UsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.readings == []

    def test_from_dict_defaults(self):
        d = _make_super_data().as_dict()
        restored = UsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.readings == []
        assert restored.last_refill is None

    def test_from_dict_returns_none_for_bad_base(self):
        result = UsageStoredData.from_dict({})
        assert result is None

    def test_as_dict_includes_readings(self):
        readings = [{"t": "2025-06-15T12:00:00+00:00", "v": 500.0}]
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=readings,
        )
        d = data.as_dict()

        assert "readings" in d
        assert d["readings"] == readings

    def test_round_trip_with_last_refill(self):
        readings = [{"t": "2025-06-15T12:00:00+00:00", "v": 500.0}]
        refill = {
            "timestamp": "2025-06-15T12:00:00+00:00",
            "volume_before": 400.0,
            "volume_after": 600.0,
            "litres_added": 200.0,
        }
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=readings,
            last_refill=refill,
        )
        d = data.as_dict()
        restored = UsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.last_refill == refill

    def test_as_dict_includes_last_refill(self):
        refill = {
            "timestamp": "2025-06-15T12:00:00+00:00",
            "volume_before": 400.0,
            "volume_after": 600.0,
            "litres_added": 200.0,
        }
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=[],
            last_refill=refill,
        )
        d = data.as_dict()

        assert "last_refill" in d
        assert d["last_refill"] == refill

    def test_round_trip_without_last_refill(self):
        data = UsageStoredData(
            super_data=_make_super_data(),
            readings=[],
        )
        d = data.as_dict()
        restored = UsageStoredData.from_dict(d)

        assert restored is not None
        assert restored.last_refill is None
