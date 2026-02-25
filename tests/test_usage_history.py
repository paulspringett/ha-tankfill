"""Tests for UsageHistory rolling-window consumption tracking."""

from datetime import datetime, timedelta, timezone

import pytest

from custom_components.tankfill.usage_history import UsageHistory


def _dt(days_ago: float = 0, hours_ago: float = 0) -> datetime:
    """Return a timezone-aware datetime relative to a fixed 'now'."""
    now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return now - timedelta(days=days_ago, hours=hours_ago)


NOW = _dt()


class TestAddReading:
    """Test adding readings and pruning."""

    def test_adds_reading(self):
        h = UsageHistory()
        h.add_reading(_dt(), 500.0)
        assert len(h.as_list()) == 1

    def test_multiple_readings(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=2), 500.0)
        h.add_reading(_dt(days_ago=1), 490.0)
        h.add_reading(_dt(), 480.0)
        assert len(h.as_list()) == 3

    def test_prunes_old_readings(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=450), 500.0)  # older than MAX_AGE_DAYS
        h.add_reading(_dt(days_ago=399), 490.0)  # within MAX_AGE_DAYS
        h.add_reading(_dt(), 480.0)
        assert len(h.as_list()) == 2  # 450-day-old reading pruned

    def test_returns_none_for_normal_reading(self):
        h = UsageHistory()
        assert h.add_reading(_dt(days_ago=1), 500.0) is None
        assert h.add_reading(_dt(), 490.0) is None

    def test_returns_none_for_first_reading(self):
        h = UsageHistory()
        assert h.add_reading(_dt(), 500.0) is None

    def test_returns_refill_dict_for_large_increase(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=1), 400.0)
        ts = _dt()
        result = h.add_reading(ts, 600.0)
        assert result is not None
        assert result["timestamp"] == ts.isoformat()
        assert result["volume_before"] == 400.0
        assert result["volume_after"] == 600.0
        assert result["litres_added"] == 200.0

    def test_increase_at_threshold_not_flagged(self):
        """An increase of exactly 100L should NOT be flagged as a refill."""
        h = UsageHistory()
        h.add_reading(_dt(days_ago=1), 500.0)
        assert h.add_reading(_dt(), 600.0) is None

    def test_increase_just_above_threshold_flagged(self):
        """An increase of 100.1L should be flagged as a refill."""
        h = UsageHistory()
        h.add_reading(_dt(days_ago=1), 500.0)
        result = h.add_reading(_dt(), 600.1)
        assert result is not None
        assert result["litres_added"] == pytest.approx(100.1)

    def test_small_increase_not_flagged(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=1), 500.0)
        assert h.add_reading(_dt(), 550.0) is None


class TestUsageSince:
    """Test consumption calculation over rolling windows."""

    def test_simple_consumption(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=3), 500.0)
        h.add_reading(_dt(days_ago=2), 490.0)
        h.add_reading(_dt(days_ago=1), 480.0)
        assert h.usage_since(_dt(days_ago=7)) == pytest.approx(20.0)

    def test_refill_ignored(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=3), 500.0)
        h.add_reading(_dt(days_ago=2), 490.0)  # consumed 10
        h.add_reading(_dt(days_ago=1), 800.0)  # refill
        h.add_reading(_dt(), 780.0)  # consumed 20
        assert h.usage_since(_dt(days_ago=7)) == pytest.approx(30.0)

    def test_no_readings_returns_zero(self):
        h = UsageHistory()
        assert h.usage_since(_dt(days_ago=7)) == 0.0

    def test_single_reading_returns_zero(self):
        h = UsageHistory()
        h.add_reading(_dt(), 500.0)
        assert h.usage_since(_dt(days_ago=7)) == 0.0

    def test_no_consumption_returns_zero(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=2), 500.0)
        h.add_reading(_dt(days_ago=1), 500.0)
        h.add_reading(_dt(), 500.0)
        assert h.usage_since(_dt(days_ago=7)) == 0.0

    def test_straddling_reading_included(self):
        """A reading just before the window should anchor consumption."""
        h = UsageHistory()
        h.add_reading(_dt(days_ago=10), 500.0)  # before 7-day window
        h.add_reading(_dt(days_ago=5), 480.0)  # inside window
        # Consumption from 500→480 = 20, and the pre-window reading anchors it
        assert h.usage_since(_dt(days_ago=7)) == pytest.approx(20.0)

    def test_weekly_window(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=10), 500.0)  # outside 7-day window
        h.add_reading(_dt(days_ago=8), 490.0)   # outside, but becomes the anchor
        h.add_reading(_dt(days_ago=5), 480.0)   # inside
        h.add_reading(_dt(days_ago=1), 470.0)   # inside
        # Anchor is 490 at day 8. Inside: 480, 470
        # 490→480 = 10, 480→470 = 10 → total 20
        assert h.usage_since(_dt(days_ago=7)) == pytest.approx(20.0)

    def test_monthly_window(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=35), 500.0)  # anchor
        h.add_reading(_dt(days_ago=25), 480.0)
        h.add_reading(_dt(days_ago=15), 460.0)
        h.add_reading(_dt(days_ago=5), 440.0)
        assert h.usage_since(_dt(days_ago=30)) == pytest.approx(60.0)

    def test_yearly_window(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=370), 1000.0)  # anchor (within MAX_AGE_DAYS)
        h.add_reading(_dt(days_ago=300), 900.0)
        h.add_reading(_dt(days_ago=200), 800.0)
        h.add_reading(_dt(days_ago=100), 700.0)
        h.add_reading(_dt(), 600.0)
        assert h.usage_since(_dt(days_ago=365)) == pytest.approx(400.0)

    def test_only_readings_outside_window(self):
        """If all readings are before the window, no consumption in window."""
        h = UsageHistory()
        h.add_reading(_dt(days_ago=20), 500.0)
        h.add_reading(_dt(days_ago=15), 490.0)
        # 7-day window has no readings inside, only an anchor
        assert h.usage_since(_dt(days_ago=7)) == 0.0

    def test_mixed_refills_and_consumption(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=6), 500.0)
        h.add_reading(_dt(days_ago=5), 490.0)   # -10
        h.add_reading(_dt(days_ago=4), 900.0)   # refill
        h.add_reading(_dt(days_ago=3), 880.0)   # -20
        h.add_reading(_dt(days_ago=2), 870.0)   # -10
        h.add_reading(_dt(days_ago=1), 1000.0)  # refill
        h.add_reading(_dt(), 985.0)              # -15
        assert h.usage_since(_dt(days_ago=7)) == pytest.approx(55.0)


class TestSerialization:
    """Test as_list / from_list round-trip."""

    def test_round_trip(self):
        h = UsageHistory()
        h.add_reading(_dt(days_ago=2), 500.0)
        h.add_reading(_dt(days_ago=1), 490.0)
        h.add_reading(_dt(), 480.0)

        data = h.as_list()
        restored = UsageHistory.from_list(data)
        assert restored.usage_since(_dt(days_ago=7)) == pytest.approx(20.0)

    def test_empty_round_trip(self):
        h = UsageHistory()
        data = h.as_list()
        assert data == []
        restored = UsageHistory.from_list(data)
        assert restored.usage_since(_dt(days_ago=7)) == 0.0

    def test_serialized_format(self):
        h = UsageHistory()
        h.add_reading(_dt(), 500.0)
        data = h.as_list()
        assert len(data) == 1
        assert "t" in data[0]
        assert "v" in data[0]
        assert data[0]["v"] == 500.0
