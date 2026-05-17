"""Tests for RssiHistory."""
from bluelock.rssi_history import RssiHistory, RssiSample


def _s(ts: float, rssi: int = -60, source: str = "dbus") -> RssiSample:
    return RssiSample(ts=ts, rssi=rssi, source=source)


def test_add_and_retrieve():
    h = RssiHistory(window_s=60)
    h.add("hci0", _s(100.0, -60))
    assert h.samples("hci0") == [_s(100.0, -60)]


def test_prune_by_time():
    h = RssiHistory(window_s=10)
    h.add("hci0", _s(100.0, -60))
    h.add("hci0", _s(105.0, -55))
    h.add("hci0", _s(115.0, -50))  # triggers pruning of ts=100
    result = h.samples("hci0")
    assert all(s.ts >= 105.0 for s in result)
    assert _s(100.0, -60) not in result


def test_window_sub_slice():
    h = RssiHistory(window_s=900)
    for i in range(20):
        h.add("hci0", _s(float(i), -60))
    # Ask for only the last 5 seconds relative to the most recent sample (ts=19)
    result = h.samples("hci0", window_s=5)
    assert all(s.ts >= 14.0 for s in result)


def test_multi_adapter_isolation():
    h = RssiHistory()
    h.add("hci0", _s(1.0, -60))
    h.add("hci1", _s(1.0, -70))
    assert len(h.samples("hci0")) == 1
    assert len(h.samples("hci1")) == 1
    assert h.samples("hci0")[0].rssi == -60
    assert h.samples("hci1")[0].rssi == -70


def test_empty_window_read():
    h = RssiHistory()
    assert h.samples("hci0") == []


def test_adapters_lists_nonempty_only():
    h = RssiHistory()
    h.add("hci0", _s(1.0))
    h.add("hci1", _s(2.0))
    assert set(h.adapters()) == {"hci0", "hci1"}


def test_adapters_empty():
    h = RssiHistory()
    assert h.adapters() == []


def test_full_window_default():
    h = RssiHistory(window_s=900)
    h.add("hci0", _s(0.0))
    h.add("hci0", _s(900.0))
    # Both are within the window (900 - 0 == window_s boundary; cutoff=0 so ts=0 is included)
    result = h.samples("hci0")
    assert len(result) == 2
