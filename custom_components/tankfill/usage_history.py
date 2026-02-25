"""Rolling-window usage history for oil consumption tracking."""

from __future__ import annotations

from datetime import datetime, timedelta


class UsageHistory:
    """Tracks volume readings and calculates consumption over rolling windows.

    Consumption is the sum of volume decreases between consecutive readings.
    Volume increases (refills) are ignored.
    """

    MAX_AGE_DAYS = 400  # buffer beyond 365

    def __init__(self, readings: list[tuple[str, float]] | None = None) -> None:
        """Initialise with optional existing readings.

        Args:
            readings: list of (iso_timestamp_str, volume_float) tuples,
                      ordered oldest-first.
        """
        self._readings: list[tuple[str, float]] = readings or []

    def add_reading(self, timestamp: datetime, volume: float) -> None:
        """Append a reading and prune entries older than MAX_AGE_DAYS."""
        self._readings.append((timestamp.isoformat(), volume))
        cutoff = (timestamp - timedelta(days=self.MAX_AGE_DAYS)).isoformat()
        self._readings = [
            (ts, vol) for ts, vol in self._readings if ts >= cutoff
        ]

    def usage_since(self, since: datetime) -> float:
        """Calculate total consumption within the window starting at *since*.

        Includes the last reading before the window to capture consumption
        that straddles the boundary.
        """
        since_iso = since.isoformat()

        # Find readings in window, plus the last one before it
        before_window: tuple[str, float] | None = None
        in_window: list[tuple[str, float]] = []

        for ts, vol in self._readings:
            if ts < since_iso:
                before_window = (ts, vol)
            else:
                in_window.append((ts, vol))

        # Build the sequence to walk: [last-before-window] + [in-window]
        sequence: list[tuple[str, float]] = []
        if before_window is not None:
            sequence.append(before_window)
        sequence.extend(in_window)

        if len(sequence) < 2:
            return 0.0

        usage = 0.0
        for i in range(1, len(sequence)):
            prev_vol = sequence[i - 1][1]
            curr_vol = sequence[i][1]
            if curr_vol < prev_vol:
                usage += prev_vol - curr_vol

        return usage

    def as_list(self) -> list[dict[str, str | float]]:
        """Serialise readings for persistence."""
        return [{"t": ts, "v": vol} for ts, vol in self._readings]

    @classmethod
    def from_list(cls, data: list[dict[str, str | float]]) -> UsageHistory:
        """Restore from serialised data."""
        readings = [(d["t"], float(d["v"])) for d in data]
        return cls(readings)
