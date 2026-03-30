"""Tests for Bluetooth utilities."""
import subprocess
from bluelock.bluetooth import _utils

def test_btmgmt_rssi_caching(mocker):
    # Reset internal state
    _utils._btmgmt_available = True

    # Mock subprocess.run to raise FileNotFoundError
    mock_run = mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    # First call should try to run and then disable
    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not found" in err
    assert _utils._btmgmt_available is False
    assert mock_run.call_count == 1

    # Second call should return immediately without calling subprocess.run
    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1

def test_btmgmt_rssi_sudo_password_caching(mocker):
    # Reset internal state
    _utils._btmgmt_available = True

    # Mock subprocess.run to return "sudo: a password is required"
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=["sudo", "-n", "btmgmt"],
        returncode=1,
        stdout="",
        stderr="sudo: a password is required\n"
    )

    # First call should try to run and then disable
    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "password is required" in err
    assert _utils._btmgmt_available is False
    assert mock_run.call_count == 1

    # Second call should return immediately
    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1

def test_hcitool_rssi_caching(mocker):
    # Reset internal state
    _utils._hcitool_available = True

    # Mock subprocess.run to raise FileNotFoundError
    mock_run = mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    # First call should try to run and then disable
    res, err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not found" in err
    assert _utils._hcitool_available is False
    assert mock_run.call_count == 1

    # Second call should return immediately
    res, err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1
