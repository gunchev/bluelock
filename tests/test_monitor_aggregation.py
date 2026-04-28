"""Tests for multi-adapter RSSI aggregation in BluezDBusMonitor."""
import pytest

from bluelock.bluetooth._adapters import AdapterInfo
from bluelock.bluetooth._bluez_dbus import BluezDBusMonitor, _AdapterState

ADDR1 = "AA:BB:CC:DD:EE:01"
ADDR2 = "AA:BB:CC:DD:EE:02"
TARGET_MAC = "11:22:33:44:55:66"


def _ainfo(addr: str, hci: str) -> AdapterInfo:
    return AdapterInfo(address=addr, path=f"/org/bluez/{hci}", alias=hci, powered=True)


@pytest.fixture
def clock():
    """Manual clock; tests advance it directly."""
    state = {"now": 1000.0}

    def _read() -> float:
        return state["now"]

    _read.advance = lambda dt: state.update(now=state["now"] + dt)  # type: ignore[attr-defined]
    return _read


@pytest.fixture
def monitor(qapp, clock):
    mon = BluezDBusMonitor(clock=clock)
    mon._target_mac = TARGET_MAC
    mon._monitoring = True
    # Pre-populate two bound adapters without going through D-Bus.
    a1 = _ainfo(ADDR1, "hci0")
    a2 = _ainfo(ADDR2, "hci1")
    mon._adapter_states[ADDR1] = _AdapterState(
        info=a1, device_path=f"{a1.path}/dev_11_22_33_44_55_66"
    )
    mon._adapter_states[ADDR2] = _AdapterState(
        info=a2, device_path=f"{a2.path}/dev_11_22_33_44_55_66"
    )
    return mon


@pytest.fixture
def captured(monitor):
    """Capture all aggregate-relevant signals."""
    rec = {
        "rssi": [],
        "per_adapter": [],
        "appeared": 0,
        "disappeared": 0,
    }
    monitor.rssi_updated.connect(lambda v: rec["rssi"].append(v))
    monitor.adapter_rssi_updated.connect(lambda a, v: rec["per_adapter"].append((a, v)))
    monitor.device_appeared.connect(lambda: rec.update(appeared=rec["appeared"] + 1))
    monitor.device_disappeared.connect(lambda: rec.update(disappeared=rec["disappeared"] + 1))
    return rec


# --------------------------------------------------------------------------- #
# Aggregation                                                                   #
# --------------------------------------------------------------------------- #


def test_aggregate_takes_max_rssi(monitor, captured):
    monitor._handle_rssi(ADDR1, -70, source="dbus")
    monitor._handle_rssi(ADDR2, -50, source="dbus")
    # Aggregate should reflect the strongest signal (highest dBm)
    assert captured["rssi"][-1] == -50


def test_aggregate_per_adapter_signal_emitted(monitor, captured):
    monitor._handle_rssi(ADDR1, -70, source="dbus")
    monitor._handle_rssi(ADDR2, -55, source="dbus")
    assert captured["per_adapter"] == [(ADDR1, -70), (ADDR2, -55)]


def test_first_sighting_emits_device_appeared_once(monitor, captured):
    monitor._handle_rssi(ADDR1, -60, source="dbus")
    monitor._handle_rssi(ADDR2, -50, source="dbus")
    monitor._handle_rssi(ADDR1, -55, source="dbus")
    assert captured["appeared"] == 1
    assert captured["disappeared"] == 0


def test_disappeared_only_when_all_adapters_stale(monitor, captured, clock):
    monitor._handle_rssi(ADDR1, -60, source="dbus")
    monitor._handle_rssi(ADDR2, -50, source="dbus")
    assert captured["appeared"] == 1

    # ADDR1 goes stale; ADDR2 is still fresh
    clock.advance(6.0)
    monitor._handle_rssi(ADDR2, -52, source="dbus")  # ADDR2 stays fresh
    assert captured["disappeared"] == 0

    # Now both go stale
    clock.advance(6.0)
    monitor._recompute_aggregate()
    assert captured["disappeared"] == 1


def test_connected_marks_present_without_rssi(monitor, captured):
    monitor._handle_connected(ADDR1, True)
    assert captured["appeared"] == 1
    monitor._handle_connected(ADDR1, False)
    assert captured["disappeared"] == 1


def test_connected_on_one_keeps_present_when_other_stale(monitor, captured, clock):
    monitor._handle_rssi(ADDR1, -60, source="dbus")
    monitor._handle_connected(ADDR2, True)
    assert captured["appeared"] == 1

    clock.advance(10.0)
    monitor._recompute_aggregate()
    # ADDR2 still Connected=true, so aggregate stays present
    assert captured["disappeared"] == 0


def test_unknown_adapter_address_ignored(monitor, captured):
    monitor._handle_rssi("DE:AD:BE:EF:00:00", -40, source="dbus")
    assert captured["per_adapter"] == []
    assert captured["rssi"] == []


def test_source_switch_logs_and_marks_using_poll(monitor, captured):
    monitor._handle_rssi(ADDR1, -60, source="btmgmt")
    state = monitor._adapter_states[ADDR1]
    assert state.using_poll is True
    assert state.poll_tool == "btmgmt"

    monitor._handle_rssi(ADDR1, -55, source="dbus")
    assert state.using_poll is False
    assert state.poll_tool == ""


def test_no_emit_when_no_fresh_samples(monitor, captured, clock):
    monitor._handle_rssi(ADDR1, -60, source="dbus")
    captured["rssi"].clear()
    captured["per_adapter"].clear()

    clock.advance(10.0)
    monitor._recompute_aggregate()
    # No fresh sample ⇒ no rssi_updated emission
    assert captured["rssi"] == []


def test_aggregate_recomputes_after_unbind(monitor, captured):
    monitor._handle_rssi(ADDR1, -70, source="dbus")
    monitor._handle_rssi(ADDR2, -50, source="dbus")
    assert captured["appeared"] == 1

    # Simulate ADDR2 going away (e.g., dongle unplugged): unbind directly.
    monitor._unbind_adapter(ADDR2, adapter_gone=True)

    # ADDR1 still has a fresh sample, so device should still be present.
    assert captured["disappeared"] == 0
    # Recompute should reflect ADDR1's value as the new best.
    monitor._recompute_aggregate()
    assert captured["rssi"][-1] == -70


def test_unbind_last_present_adapter_emits_disappeared(monitor, captured):
    monitor._handle_rssi(ADDR1, -60, source="dbus")
    assert captured["appeared"] == 1

    # Remove the only present adapter (ADDR2 has no samples yet)
    monitor._unbind_adapter(ADDR2, adapter_gone=True)
    assert captured["disappeared"] == 0   # ADDR1 still fresh

    monitor._unbind_adapter(ADDR1, adapter_gone=True)
    assert captured["disappeared"] == 1
