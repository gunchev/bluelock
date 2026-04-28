"""Tests for the adapter selection logic in the config dialog."""
from bluelock.bluetooth._adapters import AdapterInfo
from bluelock.config_dialog import _AdaptersGroup, _merge_adapter_rows


def _ainfo(addr: str, hci: str, *, alias: str = "", powered: bool = True) -> AdapterInfo:
    return AdapterInfo(address=addr, path=f"/org/bluez/{hci}", alias=alias or hci, powered=powered)


# --------------------------------------------------------------------------- #
# _merge_adapter_rows                                                           #
# --------------------------------------------------------------------------- #


def test_merge_orders_available_first_then_missing():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0"), _ainfo("AA:BB:CC:DD:EE:02", "hci1")]
    rows = _merge_adapter_rows(available, ["AA:BB:CC:DD:EE:99"])
    assert [r.address for r in rows] == [
        "AA:BB:CC:DD:EE:01",
        "AA:BB:CC:DD:EE:02",
        "AA:BB:CC:DD:EE:99",
    ]


def test_merge_marks_configured_as_checked():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0"), _ainfo("AA:BB:CC:DD:EE:02", "hci1")]
    rows = _merge_adapter_rows(available, ["AA:BB:CC:DD:EE:02"])
    by_addr = {r.address: r for r in rows}
    assert by_addr["AA:BB:CC:DD:EE:01"].checked is False
    assert by_addr["AA:BB:CC:DD:EE:02"].checked is True


def test_merge_missing_adapter_kept_and_checked():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0")]
    rows = _merge_adapter_rows(available, ["AA:BB:CC:DD:EE:99"])
    missing = next(r for r in rows if r.address == "AA:BB:CC:DD:EE:99")
    assert missing.available is False
    assert missing.checked is True
    assert "(unavailable)" in missing.display_text()


def test_merge_skips_adapters_with_blank_address():
    available = [_ainfo("", "hci0"), _ainfo("AA:BB:CC:DD:EE:01", "hci1")]
    rows = _merge_adapter_rows(available, [])
    assert [r.address for r in rows] == ["AA:BB:CC:DD:EE:01"]


def test_merge_normalises_configured_input():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0")]
    rows = _merge_adapter_rows(available, ["aa-bb-cc-dd-ee-01"])
    assert rows[0].checked is True


def test_merge_drops_invalid_configured_addresses():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0")]
    rows = _merge_adapter_rows(available, ["not-a-mac"])
    # Single row from `available`, no extra row from the bad input
    assert [r.address for r in rows] == ["AA:BB:CC:DD:EE:01"]
    assert rows[0].checked is False


def test_merge_empty_inputs():
    assert _merge_adapter_rows([], []) == []


def test_display_text_includes_powered_indicator():
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0", alias="laptop", powered=False)]
    rows = _merge_adapter_rows(available, [])
    assert "(off)" in rows[0].display_text()


# --------------------------------------------------------------------------- #
# _AdaptersGroup widget                                                         #
# --------------------------------------------------------------------------- #


def test_adapters_group_round_trip(qapp, mocker):
    available = [
        _ainfo("AA:BB:CC:DD:EE:01", "hci0"),
        _ainfo("AA:BB:CC:DD:EE:02", "hci1"),
    ]
    mocker.patch("bluelock.config_dialog.list_adapters", return_value=available)

    group = _AdaptersGroup()
    group.set_configured(["AA:BB:CC:DD:EE:02"])
    assert group.selected_addresses() == ["AA:BB:CC:DD:EE:02"]


def test_adapters_group_preserves_missing_selection(qapp, mocker):
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0")]
    mocker.patch("bluelock.config_dialog.list_adapters", return_value=available)

    group = _AdaptersGroup()
    group.set_configured(["AA:BB:CC:DD:EE:99"])
    # The configured-but-missing adapter remains in the selection.
    assert "AA:BB:CC:DD:EE:99" in group.selected_addresses()


def test_adapters_group_empty_selection_means_all(qapp, mocker):
    available = [_ainfo("AA:BB:CC:DD:EE:01", "hci0"), _ainfo("AA:BB:CC:DD:EE:02", "hci1")]
    mocker.patch("bluelock.config_dialog.list_adapters", return_value=available)

    group = _AdaptersGroup()
    group.set_configured([])
    assert group.selected_addresses() == []


def test_adapters_group_refresh_picks_up_new_adapter(qapp, mocker):
    patched = mocker.patch("bluelock.config_dialog.list_adapters",
                           return_value=[_ainfo("AA:BB:CC:DD:EE:01", "hci0")])

    group = _AdaptersGroup()
    group.set_configured(["AA:BB:CC:DD:EE:01"])
    assert group.selected_addresses() == ["AA:BB:CC:DD:EE:01"]

    # Hot-plug: a second adapter appears.
    patched.return_value = [
        _ainfo("AA:BB:CC:DD:EE:01", "hci0"),
        _ainfo("AA:BB:CC:DD:EE:02", "hci1"),
    ]
    group.refresh()
    # Existing checked state preserved; new adapter starts unchecked.
    assert group.selected_addresses() == ["AA:BB:CC:DD:EE:01"]
