"""Tests for bluelock.state_machine."""
import time

import pytest

from bluelock.state_machine import ProximityState, ProximityStateMachine

LOCK_RSSI = -15
UNLOCK_RSSI = -10


@pytest.fixture
def sm(monkeypatch):
    # Fix monotonic time for predictable tests
    current_time = [100.0]
    def mock_monotonic():
        return current_time[0]
    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    sm = ProximityStateMachine(
        lock_rssi_threshold=LOCK_RSSI,
        lock_duration=3.0,
        unlock_rssi_threshold=UNLOCK_RSSI,
        unlock_duration=2.0,
    )
    # Add a helper to advance time
    def advance(seconds):
        current_time[0] += seconds
    sm.advance = advance
    return sm


class TestInitialState:
    def test_starts_unknown(self, sm):
        assert sm.state == ProximityState.UNKNOWN

    def test_first_reading_close_sets_active(self, sm):
        result = sm.evaluate(-5, device_present=True)
        assert result == ProximityState.ACTIVE
        assert sm.state == ProximityState.ACTIVE

    def test_first_reading_far_sets_gone(self, sm):
        result = sm.evaluate(-80, device_present=True)
        assert result == ProximityState.GONE
        assert sm.state == ProximityState.GONE

    def test_first_reading_absent_sets_gone(self, sm):
        result = sm.evaluate(-80, device_present=False)
        assert result == ProximityState.GONE

    def test_first_reading_does_not_return_none(self, sm):
        result = sm.evaluate(-5, device_present=True)
        assert result is not None


class TestActiveToGone:
    def test_weak_signal_for_duration_locks(self, sm):
        sm.evaluate(-5, True)   # → ACTIVE
        assert sm.evaluate(-20, True) is None    # 0s elapsed
        sm.advance(1.5)
        assert sm.evaluate(-20, True) is None    # 1.5s elapsed
        sm.advance(1.5)
        result = sm.evaluate(-20, True)           # 3.0s elapsed (lock_duration=3)
        assert result == ProximityState.GONE

    def test_absent_device_counts_toward_lock(self, sm):
        sm.evaluate(-5, True)   # → ACTIVE
        assert sm.evaluate(-80, False) is None
        sm.advance(3.0)
        result = sm.evaluate(-80, False)
        assert result == ProximityState.GONE

    def test_signal_recovery_resets_counter(self, sm):
        sm.evaluate(-5, True)   # → ACTIVE
        sm.evaluate(-20, True)  # start timer
        sm.advance(2.0)
        sm.evaluate(-5, True)   # signal recovers — timer resets
        sm.advance(1.0)
        assert sm.evaluate(-20, True) is None  # timer starts fresh
        sm.advance(3.0)
        result = sm.evaluate(-20, True)        # 3.0s total below threshold
        assert result == ProximityState.GONE

    def test_stays_active_if_threshold_not_met(self, sm):
        sm.evaluate(-5, True)   # → ACTIVE
        for _ in range(10):
            sm.advance(1.0)
            result = sm.evaluate(-12, True)  # above lock threshold (-15)
            assert result is None
        assert sm.state == ProximityState.ACTIVE

    def test_exactly_at_lock_threshold_triggers(self, sm):
        sm.evaluate(-5, True)   # → ACTIVE
        sm.evaluate(LOCK_RSSI, True)  # start timer
        sm.advance(3.0)
        sm.evaluate(LOCK_RSSI, True)
        assert sm.state == ProximityState.GONE


class TestGoneToActive:
    def test_strong_signal_for_duration_unlocks(self, sm):
        sm.evaluate(-80, True)  # → GONE
        assert sm.evaluate(-5, True) is None     # start timer (unlock_duration=2)
        sm.advance(2.0)
        result = sm.evaluate(-5, True)            # 2nd
        assert result == ProximityState.ACTIVE

    def test_signal_drop_resets_unlock_counter(self, sm):
        sm.evaluate(-80, True)  # → GONE
        sm.evaluate(-5, True)   # start timer
        sm.advance(1.0)
        sm.evaluate(-80, True)  # signal drops — resets
        sm.advance(1.0)
        assert sm.evaluate(-5, True) is None  # timer starts fresh
        sm.advance(2.0)
        result = sm.evaluate(-5, True)         # 2.0s
        assert result == ProximityState.ACTIVE

    def test_absent_device_does_not_unlock(self, sm):
        sm.evaluate(-80, True)  # → GONE
        sm.evaluate(-5, False)  # strong RSSI but not present
        sm.advance(5.0)
        result = sm.evaluate(-5, False)
        assert result is None
        assert sm.state == ProximityState.GONE

    def test_stays_gone_if_threshold_not_met(self, sm):
        sm.evaluate(-80, True)  # → GONE
        for _ in range(10):
            sm.advance(1.0)
            result = sm.evaluate(-12, True)  # below unlock threshold (-10)
            assert result is None
        assert sm.state == ProximityState.GONE

    def test_exactly_at_unlock_threshold_triggers(self, sm):
        sm.evaluate(-80, True)  # → GONE
        sm.evaluate(UNLOCK_RSSI, True)
        sm.advance(2.0)
        sm.evaluate(UNLOCK_RSSI, True)
        assert sm.state == ProximityState.ACTIVE


class TestReset:
    def test_reset_returns_to_unknown(self, sm):
        sm.evaluate(-5, True)
        sm.reset()
        assert sm.state == ProximityState.UNKNOWN

    def test_after_reset_first_reading_sets_state(self, sm):
        sm.evaluate(-5, True)
        sm.reset()
        result = sm.evaluate(-80, True)
        assert result == ProximityState.GONE


class TestHysteresis:
    """Verify that separate lock/unlock thresholds prevent oscillation."""

    def test_no_oscillation_between_thresholds(self, sm):
        """Signal hovering between thresholds should not cause state changes."""
        sm.evaluate(-5, True)   # → ACTIVE
        mid_signal = (LOCK_RSSI + UNLOCK_RSSI) / 2  # e.g., -12.5, between -15 and -10
        for _ in range(20):
            result = sm.evaluate(mid_signal, True)
            assert result is None
        assert sm.state == ProximityState.ACTIVE
