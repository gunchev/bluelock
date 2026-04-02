"""Tests for bluelock.signal_processor."""
import pytest

from bluelock.signal_processor import NO_SIGNAL, SignalProcessor


class TestSignalProcessorBuffer:
    def test_empty_has_no_readings(self):
        sp = SignalProcessor()
        assert not sp.has_readings

    def test_add_reading_sets_has_readings(self):
        sp = SignalProcessor()
        sp.add_reading(-50)
        assert sp.has_readings

    def test_last_raw_empty(self):
        sp = SignalProcessor()
        assert sp.last_raw == NO_SIGNAL

    def test_last_raw_returns_most_recent(self):
        sp = SignalProcessor()
        sp.add_reading(-60)
        sp.add_reading(-40)
        assert sp.last_raw == -40

    def test_buffer_size_limits_readings(self):
        sp = SignalProcessor(buffer_size=3)
        for v in [-70, -60, -50, -40]:
            sp.add_reading(v)
        assert sp.last_raw == -40
        # Only last 3 values affect smoothed; first value (-70) is evicted
        assert sp.smoothed_rssi > -60

    def test_reset_clears_buffer(self):
        sp = SignalProcessor()
        sp.add_reading(-50)
        sp.reset()
        assert not sp.has_readings
        assert sp.last_raw == NO_SIGNAL

    def test_resize_buffer_keeps_existing(self):
        sp = SignalProcessor(buffer_size=5)
        for v in [-50, -60, -70]:
            sp.add_reading(v)
        sp.buffer_size = 10
        assert sp.has_readings
        assert sp.last_raw == -70


class TestSmoothedRssi:
    def test_single_reading(self):
        sp = SignalProcessor()
        sp.add_reading(-55)
        assert sp.smoothed_rssi == pytest.approx(-55.0)

    def test_empty_returns_no_signal(self):
        sp = SignalProcessor()
        assert sp.smoothed_rssi == pytest.approx(float(NO_SIGNAL))

    def test_recent_values_weighted_more(self):
        sp = SignalProcessor(buffer_size=3)
        sp.add_reading(-80)  # old, weight 1
        sp.add_reading(-60)  # middle, weight 2
        sp.add_reading(-40)  # most recent, weight 3
        # Weighted avg: (-80*1 + -60*2 + -40*3) / (1+2+3) = (-80-120-120)/6 = -320/6 ≈ -53.3
        assert sp.smoothed_rssi == pytest.approx(-320 / 6, rel=1e-6)

    def test_stable_signal_equals_value(self):
        sp = SignalProcessor(buffer_size=5)
        for _ in range(5):
            sp.add_reading(-65)
        assert sp.smoothed_rssi == pytest.approx(-65.0)


class TestDistanceEstimation:
    def test_at_one_metre(self):
        # At tx_power (-59 dBm), distance should be ~1 m
        sp = SignalProcessor()
        sp.add_reading(-59)
        assert sp.estimated_distance_m == pytest.approx(1.0, rel=0.01)

    def test_closer_means_higher_rssi(self):
        sp_near = SignalProcessor()
        sp_near.add_reading(-30)
        sp_far = SignalProcessor()
        sp_far.add_reading(-80)
        assert sp_near.estimated_distance_m < sp_far.estimated_distance_m

    def test_no_signal_returns_large_distance(self):
        sp = SignalProcessor()
        assert sp.estimated_distance_m == pytest.approx(1000.0)

    def test_distance_positive(self):
        sp = SignalProcessor()
        for rssi in [-20, -50, -80, -100]:
            sp.reset()
            sp.add_reading(rssi)
            assert sp.estimated_distance_m > 0
