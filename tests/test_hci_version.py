"""Tests for hci_version() sysfs reader."""
import pathlib

import bluelock.bluetooth._adapters as _mod
from bluelock.bluetooth._adapters import hci_version


def _write_sysfs(base: pathlib.Path, hci_name: str, content: str) -> None:
    d = base / hci_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "hci_version").write_text(content)


def test_known_bytes(tmp_path, monkeypatch):
    expected = {6: "4.0", 7: "4.1", 8: "4.2", 9: "5.0", 10: "5.1", 11: "5.2", 12: "5.3", 13: "5.4"}
    monkeypatch.setattr(_mod, "_SYS_BT", tmp_path)
    for byte, version in expected.items():
        hci_name = f"hci{byte}"
        _write_sysfs(tmp_path, hci_name, str(byte))
        assert hci_version(hci_name) == version


def test_unknown_byte(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "_SYS_BT", tmp_path)
    _write_sysfs(tmp_path, "hci0", "99")
    assert hci_version("hci0") is None


def test_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "_SYS_BT", tmp_path)
    assert hci_version("hci99") is None


def test_non_integer_content(tmp_path, monkeypatch):
    monkeypatch.setattr(_mod, "_SYS_BT", tmp_path)
    _write_sysfs(tmp_path, "hci0", "not-a-number")
    assert hci_version("hci0") is None
