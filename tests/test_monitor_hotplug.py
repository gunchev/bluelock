"""Tests for adapter hot-plug handling in BluezDBusMonitor."""
import pytest

from bluelock.bluetooth._adapters import AdapterInfo
from bluelock.bluetooth._bluez_dbus import BluezDBusMonitor

ADDR1 = "AA:BB:CC:DD:EE:01"
ADDR2 = "AA:BB:CC:DD:EE:02"
ADDR3 = "AA:BB:CC:DD:EE:03"
TARGET_MAC = "11:22:33:44:55:66"


def _ainfo(addr: str, hci: str, *, powered: bool = True) -> AdapterInfo:
    return AdapterInfo(address=addr, path=f"/org/bluez/{hci}", alias=hci, powered=powered)


@pytest.fixture
def monitor(qapp, mocker):
    """Monitor with all D-Bus side-effects mocked out."""
    mon = BluezDBusMonitor()
    # Stub D-Bus interactions so handlers don't try to talk to BlueZ.
    mocker.patch.object(mon, "_start_discovery")
    mocker.patch.object(mon, "_stop_discovery")
    mocker.patch.object(mon, "_connect_device_signals")
    mocker.patch.object(mon, "_disconnect_device_signals")
    mocker.patch.object(mon, "_connect_adapter_props")
    mocker.patch.object(mon, "_disconnect_adapter_props")
    mocker.patch.object(mon, "_connect_object_manager_signals")
    mocker.patch.object(mon, "_disconnect_object_manager_signals")
    return mon


def _start(monitor: BluezDBusMonitor, mocker, *, selected: list[str] | None = None,
           available: list[AdapterInfo] | None = None) -> None:
    """Bypass real adapter resolution; just inject what the test wants bound."""
    available = available if available is not None else [_ainfo(ADDR1, "hci0"), _ainfo(ADDR2, "hci1")]
    mocker.patch("bluelock.bluetooth._bluez_dbus.list_adapters", return_value=available)
    monitor.start_monitoring(TARGET_MAC, selected)


# --------------------------------------------------------------------------- #
# Bind set determined by selection                                              #
# --------------------------------------------------------------------------- #


def test_empty_selection_binds_all_available(monitor, mocker):
    _start(monitor, mocker, selected=[])
    bound = {a.address for a in monitor.bound_adapters}
    assert bound == {ADDR1, ADDR2}


def test_explicit_selection_binds_only_listed(monitor, mocker):
    _start(monitor, mocker, selected=[ADDR2])
    bound = {a.address for a in monitor.bound_adapters}
    assert bound == {ADDR2}


def test_unpowered_adapter_skipped_at_bind(monitor, mocker):
    available = [_ainfo(ADDR1, "hci0", powered=False), _ainfo(ADDR2, "hci1", powered=True)]
    _start(monitor, mocker, selected=[], available=available)
    bound = {a.address for a in monitor.bound_adapters}
    assert bound == {ADDR2}


def test_missing_address_adapter_skipped(monitor, mocker):
    available = [_ainfo("", "hci0", powered=True), _ainfo(ADDR2, "hci1", powered=True)]
    _start(monitor, mocker, selected=[], available=available)
    bound = {a.address for a in monitor.bound_adapters}
    assert bound == {ADDR2}


# --------------------------------------------------------------------------- #
# Hot-plug                                                                      #
# --------------------------------------------------------------------------- #


def test_adapter_added_in_selection_binds(monitor, mocker):
    _start(monitor, mocker, selected=[ADDR1, ADDR3], available=[_ainfo(ADDR1, "hci0")])
    assert {a.address for a in monitor.bound_adapters} == {ADDR1}

    monitor._handle_adapter_added(_ainfo(ADDR3, "hci2"))
    assert {a.address for a in monitor.bound_adapters} == {ADDR1, ADDR3}


def test_adapter_added_when_auto_mode_binds(monitor, mocker):
    _start(monitor, mocker, selected=[], available=[_ainfo(ADDR1, "hci0")])
    monitor._handle_adapter_added(_ainfo(ADDR2, "hci1"))
    assert {a.address for a in monitor.bound_adapters} == {ADDR1, ADDR2}


def test_adapter_added_outside_selection_ignored(monitor, mocker):
    _start(monitor, mocker, selected=[ADDR1], available=[_ainfo(ADDR1, "hci0")])
    monitor._handle_adapter_added(_ainfo(ADDR2, "hci1"))
    assert {a.address for a in monitor.bound_adapters} == {ADDR1}


def test_adapter_added_unpowered_deferred(monitor, mocker):
    _start(monitor, mocker, selected=[], available=[_ainfo(ADDR1, "hci0")])
    monitor._handle_adapter_added(_ainfo(ADDR2, "hci1", powered=False))
    # Unpowered adapter is not bound; binds when Powered=true arrives.
    assert {a.address for a in monitor.bound_adapters} == {ADDR1}

    monitor._handle_powered("/org/bluez/hci1", True, address=ADDR2, alias="hci1")
    assert {a.address for a in monitor.bound_adapters} == {ADDR1, ADDR2}


def test_powered_on_signal_rebinds_via_cache(monitor, mocker):
    """_on_adapter_props_changed must resolve the address from _adapter_path_to_address."""
    available = [_ainfo(ADDR1, "hci0"), _ainfo(ADDR2, "hci1", powered=False)]
    _start(monitor, mocker, selected=[], available=available)
    assert {a.address for a in monitor.bound_adapters} == {ADDR1}
    # Cache is populated for both adapters including the unpowered one.
    assert monitor._adapter_path_to_address.get("/org/bluez/hci1") == ADDR2

    msg = mocker.MagicMock()
    msg.path.return_value = "/org/bluez/hci1"
    msg.arguments.return_value = ["org.bluez.Adapter1", {"Powered": True}, []]
    monitor._on_adapter_props_changed(msg)
    assert {a.address for a in monitor.bound_adapters} == {ADDR1, ADDR2}


def test_adapter_removed_unbinds(monitor, mocker):
    _start(monitor, mocker, selected=[])
    assert ADDR1 in {a.address for a in monitor.bound_adapters}
    monitor._handle_adapter_removed("/org/bluez/hci0")
    assert ADDR1 not in {a.address for a in monitor.bound_adapters}


def test_adapter_removed_for_unbound_path_is_noop(monitor, mocker):
    _start(monitor, mocker, selected=[])
    monitor._handle_adapter_removed("/org/bluez/hci99")  # never bound
    assert len(monitor.bound_adapters) == 2


def test_powered_false_unbinds(monitor, mocker):
    _start(monitor, mocker, selected=[])
    monitor._handle_powered("/org/bluez/hci0", False)
    bound = {a.address for a in monitor.bound_adapters}
    assert ADDR1 not in bound and ADDR2 in bound


def test_adapters_changed_emitted_on_bind_unbind(monitor, mocker):
    _start(monitor, mocker, selected=[])
    events = []
    monitor.adapters_changed.connect(lambda: events.append(True))
    monitor._handle_adapter_removed("/org/bluez/hci0")
    monitor._handle_adapter_added(_ainfo(ADDR3, "hci2"))
    assert len(events) == 2


# --------------------------------------------------------------------------- #
# Lifecycle                                                                     #
# --------------------------------------------------------------------------- #


def test_stop_monitoring_unbinds_all(monitor, mocker):
    _start(monitor, mocker, selected=[])
    monitor.stop_monitoring()
    assert monitor.bound_adapters == []
    assert monitor.is_monitoring is False


def test_hotplug_ignored_when_not_monitoring(monitor):
    # No start_monitoring call — monitor is idle.
    monitor._handle_adapter_added(_ainfo(ADDR1, "hci0"))
    assert monitor.bound_adapters == []
