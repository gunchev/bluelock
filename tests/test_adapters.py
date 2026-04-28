"""Tests for adapter enumeration and resolution."""
from bluelock.bluetooth._adapters import AdapterInfo, _parse_adapters, resolve_addresses

_ADAPTER_IFACE = "org.bluez.Adapter1"
_DEVICE_IFACE = "org.bluez.Device1"


def _make_objects() -> dict:
    return {
        "/org/bluez/hci0": {
            _ADAPTER_IFACE: {"Address": "AA:BB:CC:DD:EE:01", "Alias": "laptop", "Powered": True},
        },
        "/org/bluez/hci1": {
            _ADAPTER_IFACE: {"Address": "aa:bb:cc:dd:ee:02", "Alias": "USB dongle", "Powered": False},
        },
        # Non-adapter object — must be ignored
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": {
            _DEVICE_IFACE: {"Address": "AA:BB:CC:DD:EE:FF", "Name": "phone"},
        },
    }


def test_parse_adapters_extracts_fields():
    adapters = _parse_adapters(_make_objects())
    assert len(adapters) == 2
    a0, a1 = adapters
    assert a0.path == "/org/bluez/hci0"
    assert a0.address == "AA:BB:CC:DD:EE:01"
    assert a0.alias == "laptop"
    assert a0.powered is True
    assert a0.hci_name == "hci0"
    # Lower-case input is normalised to upper-case
    assert a1.address == "AA:BB:CC:DD:EE:02"
    assert a1.powered is False


def test_parse_adapters_handles_zero_address():
    objects = {
        "/org/bluez/hci0": {
            _ADAPTER_IFACE: {"Address": "00:00:00:00:00:00", "Powered": True},
        },
    }
    adapters = _parse_adapters(objects)
    assert len(adapters) == 1
    # Zero address is reported but blanked so it never matches a configured selection
    assert adapters[0].path == "/org/bluez/hci0"
    assert adapters[0].address == ""


def test_parse_adapters_sorted_by_path():
    objects = {
        "/org/bluez/hci2": {_ADAPTER_IFACE: {"Address": "AA:BB:CC:DD:EE:03"}},
        "/org/bluez/hci0": {_ADAPTER_IFACE: {"Address": "AA:BB:CC:DD:EE:01"}},
        "/org/bluez/hci1": {_ADAPTER_IFACE: {"Address": "AA:BB:CC:DD:EE:02"}},
    }
    paths = [a.path for a in _parse_adapters(objects)]
    assert paths == ["/org/bluez/hci0", "/org/bluez/hci1", "/org/bluez/hci2"]


def test_parse_adapters_returns_empty_for_no_adapters():
    assert _parse_adapters({}) == []


def test_resolve_addresses_empty_returns_all():
    adapters = _parse_adapters(_make_objects())
    resolved = resolve_addresses([], adapters=adapters)
    assert resolved == adapters


def test_resolve_addresses_filters_and_preserves_order():
    adapters = _parse_adapters(_make_objects())
    resolved = resolve_addresses(
        ["AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:01"],
        adapters=adapters,
    )
    assert [a.address for a in resolved] == ["AA:BB:CC:DD:EE:02", "AA:BB:CC:DD:EE:01"]


def test_resolve_addresses_drops_missing():
    adapters = _parse_adapters(_make_objects())
    resolved = resolve_addresses(
        ["AA:BB:CC:DD:EE:01", "DE:AD:BE:EF:00:00"],
        adapters=adapters,
    )
    assert [a.address for a in resolved] == ["AA:BB:CC:DD:EE:01"]


def test_resolve_addresses_normalises_input():
    adapters = _parse_adapters(_make_objects())
    resolved = resolve_addresses(["aa-bb-cc-dd-ee-01"], adapters=adapters)
    assert [a.address for a in resolved] == ["AA:BB:CC:DD:EE:01"]


def test_resolve_addresses_skips_invalid():
    adapters = _parse_adapters(_make_objects())
    resolved = resolve_addresses(["not-a-mac", "AA:BB:CC:DD:EE:01"], adapters=adapters)
    assert [a.address for a in resolved] == ["AA:BB:CC:DD:EE:01"]


def test_adapter_info_hci_name_blank_path():
    assert AdapterInfo(address="", path="").hci_name == ""
