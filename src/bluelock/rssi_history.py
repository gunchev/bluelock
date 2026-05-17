"""Per-adapter RSSI sample history with time-bounded storage."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RssiSample:
    ts: float    # monotonic seconds
    rssi: int    # dBm
    source: str  # "dbus" | "btmgmt" | "hcitool"


class RssiHistory:
    """Per-adapter ring buffer of RSSI samples, pruned to a configurable time window."""

    def __init__(self, window_s: float = 900) -> None:
        self._window_s = window_s
        self._data: dict[str, deque[RssiSample]] = {}

    def add(self, adapter: str, sample: RssiSample) -> None:
        if adapter not in self._data:
            self._data[adapter] = deque()
        q = self._data[adapter]
        q.append(sample)
        cutoff = sample.ts - self._window_s
        while q and q[0].ts < cutoff:
            q.popleft()

    def samples(self, adapter: str, window_s: float | None = None) -> list[RssiSample]:
        """Return samples for *adapter* within *window_s* seconds of the most recent sample.

        Uses the full configured window when *window_s* is None.
        """
        q = self._data.get(adapter)
        if not q:
            return []
        w = window_s if window_s is not None else self._window_s
        cutoff = q[-1].ts - w
        return [s for s in q if s.ts >= cutoff]

    def adapters(self) -> list[str]:
        """Return adapters that have at least one stored sample, in insertion order."""
        return [a for a, q in self._data.items() if q]
