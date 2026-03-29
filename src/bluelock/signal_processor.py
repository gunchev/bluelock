"""RSSI signal smoothing and distance estimation."""
from __future__ import annotations

import collections
import math

# Typical RSSI at 1 metre for Bluetooth (device-dependent, but -59 dBm is a common default)
_TX_POWER_AT_1M = -59

# Path-loss exponent: ~2.0 outdoors, ~2.5-3.5 indoors
_PATH_LOSS_EXPONENT = 2.5

# Sentinel value meaning "no reading yet"
NO_SIGNAL = -127


class SignalProcessor:
    """Maintains a ring buffer of RSSI readings and provides smoothed values."""

    def __init__(self, buffer_size: int = 16) -> None:
        self._buffer_size = max(1, buffer_size)
        self._buffer: collections.deque[int] = collections.deque(maxlen=self._buffer_size)

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    @buffer_size.setter
    def buffer_size(self, value: int) -> None:
        new_size = max(1, value)
        if new_size != self._buffer_size:
            self._buffer_size = new_size
            self._buffer = collections.deque(self._buffer, maxlen=new_size)

    def add_reading(self, rssi: int) -> None:
        """Add a raw RSSI reading to the buffer."""
        self._buffer.append(rssi)

    @property
    def has_readings(self) -> bool:
        """True if at least one reading has been added."""
        return len(self._buffer) > 0

    @property
    def last_raw(self) -> int:
        """Most recent raw RSSI value, or NO_SIGNAL if no readings yet."""
        return self._buffer[-1] if self._buffer else NO_SIGNAL

    @property
    def smoothed_rssi(self) -> float:
        """Weighted moving average of buffered RSSI values.

        More recent readings get higher weight. Returns NO_SIGNAL if empty.
        """
        if not self._buffer:
            return float(NO_SIGNAL)

        total_weight = 0.0
        total = 0.0
        for i, value in enumerate(self._buffer):
            weight = i + 1  # older readings get weight 1, most recent gets highest
            total += value * weight
            total_weight += weight

        return total / total_weight

    @property
    def estimated_distance_m(self) -> float:
        """Estimate distance in metres using the log-distance path loss model.

        d = 10 ^ ((tx_power - rssi) / (10 * n))
        where tx_power is the RSSI at 1 metre and n is the path-loss exponent.

        Returns a large value (1000 m) when signal is absent.
        """
        rssi = self.smoothed_rssi
        if rssi <= NO_SIGNAL + 1:
            return 1000.0
        exponent = (_TX_POWER_AT_1M - rssi) / (10.0 * _PATH_LOSS_EXPONENT)
        return math.pow(10.0, exponent)

    def reset(self) -> None:
        """Clear all buffered readings."""
        self._buffer.clear()
