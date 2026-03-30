"""Proximity state machine with hysteresis for lock/unlock decisions."""
from __future__ import annotations

import enum
import logging
import time

from bluelock.signal_processor import NO_SIGNAL

log = logging.getLogger(__name__)


class ProximityState(enum.Enum):
    """State of the proximity monitor."""

    UNKNOWN = "unknown"   # No readings yet; initial state on startup
    ACTIVE = "active"     # Device is close; session should be unlocked
    GONE = "gone"         # Device is far/absent; session should be locked


class ProximityStateMachine:
    """Hysteresis state machine for proximity-based lock/unlock decisions.

    Uses separate thresholds for locking and unlocking with duration counters
    to prevent oscillation from momentary signal fluctuations.

    Transition rules:
        UNKNOWN → ACTIVE or GONE on first reading (no command executed)
        ACTIVE  → GONE  when smoothed_rssi <= lock_threshold for lock_duration seconds
        GONE    → ACTIVE when smoothed_rssi >= unlock_threshold for unlock_duration seconds
    """

    def __init__(
        self,
        lock_rssi_threshold: int = -15,
        lock_duration: float = 6.0,
        unlock_rssi_threshold: int = -10,
        unlock_duration: float = 1.0,
    ) -> None:
        self.lock_rssi_threshold = lock_rssi_threshold
        self.lock_duration = lock_duration
        self.unlock_rssi_threshold = unlock_rssi_threshold
        self.unlock_duration = unlock_duration

        self._state = ProximityState.UNKNOWN
        self._last_met_time = 0.0

    @property
    def state(self) -> ProximityState:
        return self._state

    @property
    def lock_pending(self) -> bool:
        """True while in ACTIVE state and the lock condition is met but duration hasn't elapsed."""
        return self._state == ProximityState.ACTIVE and self._last_met_time > 0

    def evaluate(
        self, smoothed_rssi: float, device_present: bool
    ) -> ProximityState | None:
        """Evaluate the current RSSI and return the new state if it changed.

        Args:
            smoothed_rssi: The smoothed/averaged RSSI value.
            device_present: Whether the device is currently visible to BlueZ.

        Returns:
            The new ProximityState if a transition occurred, else None.
            On the UNKNOWN → first-state transition, returns the new state
            but the caller should NOT execute lock/unlock commands.
        """
        # Treat absent device as very low signal
        effective_rssi = smoothed_rssi if device_present else float(NO_SIGNAL)

        if self._state == ProximityState.UNKNOWN:
            return self._handle_unknown(effective_rssi)
        if self._state == ProximityState.ACTIVE:
            return self._handle_active(effective_rssi, device_present)
        # GONE
        return self._handle_gone(effective_rssi, device_present)

    def _handle_unknown(self, effective_rssi: float) -> ProximityState | None:
        """Determine initial state from first reading without triggering actions."""
        if effective_rssi >= self.unlock_rssi_threshold:
            self._transition(ProximityState.ACTIVE)
        else:
            self._transition(ProximityState.GONE)
        log.info("Initial state determined: %s (RSSI=%.1f)", self._state.value, effective_rssi)
        return self._state

    def _handle_active(self, effective_rssi: float, device_present: bool) -> ProximityState | None:
        """Check if we should transition from ACTIVE to GONE."""
        should_lock = not device_present or effective_rssi <= self.lock_rssi_threshold
        if should_lock:
            now = time.monotonic()
            if self._last_met_time == 0:
                self._last_met_time = now

            elapsed = now - self._last_met_time
            log.debug("Lock condition met (%.1fs/%.1fs): RSSI=%.1f present=%s",
                      elapsed, self.lock_duration, effective_rssi, device_present)
            if elapsed >= self.lock_duration:
                self._transition(ProximityState.GONE)
                log.info("→ GONE (RSSI=%.1f, elapsed=%.1fs)", effective_rssi, elapsed)
                return ProximityState.GONE
        else:
            if self._last_met_time > 0:
                log.debug("Lock condition reset (RSSI=%.1f)", effective_rssi)
            self._last_met_time = 0.0
        return None

    def _handle_gone(self, effective_rssi: float, device_present: bool) -> ProximityState | None:
        """Check if we should transition from GONE to ACTIVE."""
        should_unlock = device_present and effective_rssi >= self.unlock_rssi_threshold
        if should_unlock:
            now = time.monotonic()
            if self._last_met_time == 0:
                self._last_met_time = now

            elapsed = now - self._last_met_time
            log.debug("Unlock condition met (%.1fs/%.1fs): RSSI=%.1f present=%s",
                      elapsed, self.unlock_duration, effective_rssi, device_present)
            if elapsed >= self.unlock_duration:
                self._transition(ProximityState.ACTIVE)
                log.info("→ ACTIVE (RSSI=%.1f, elapsed=%.1fs)", effective_rssi, elapsed)
                return ProximityState.ACTIVE
        else:
            if self._last_met_time > 0:
                log.debug("Unlock condition reset (RSSI=%.1f)", effective_rssi)
            self._last_met_time = 0.0
        return None

    def _transition(self, new_state: ProximityState) -> None:
        self._state = new_state
        self._last_met_time = 0.0

    def reset(self) -> None:
        """Reset to UNKNOWN state."""
        self._state = ProximityState.UNKNOWN
        self._last_met_time = 0.0
