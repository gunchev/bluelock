"""Tests for Bluetooth utilities."""
import subprocess

from bluelock.bluetooth import _utils


def test_btmgmt_rssi_caching(mocker):
    _utils._btmgmt_available.clear()

    mock_run = mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not found" in err
    assert _utils._btmgmt_available[None] is False
    assert mock_run.call_count == 1

    # Second call should return immediately without calling subprocess.run
    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1


def test_btmgmt_rssi_sudo_password_caching(mocker):
    _utils._btmgmt_available.clear()

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=["sudo", "-n", "btmgmt"],
        returncode=1,
        stdout="",
        stderr="sudo: a password is required\n"
    )

    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "password is required" in err
    assert _utils._btmgmt_available[None] is False
    assert mock_run.call_count == 1

    res, err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1


def test_hcitool_rssi_caching(mocker):
    _utils._hcitool_available.clear()

    mock_run = mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    res, err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not found" in err
    assert _utils._hcitool_available[None] is False
    assert mock_run.call_count == 1

    res, err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF")
    assert res is None
    assert "not available" in err
    assert mock_run.call_count == 1


def test_btmgmt_rssi_passes_adapter_flag(mocker):
    _utils._btmgmt_available.clear()
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="rssi -42\n", stderr="",
    )

    res, _err = _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF", adapter="hci1")
    assert res == -42
    argv = mock_run.call_args.args[0]
    assert "-i" in argv and argv[argv.index("-i") + 1] == "hci1"
    assert "conn-info" in argv


def test_hcitool_rssi_passes_adapter_flag(mocker):
    _utils._hcitool_available.clear()
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="RSSI return value: -55\n", stderr="",
    )

    res, _err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF", adapter="hci2")
    assert res == -55
    argv = mock_run.call_args.args[0]
    assert argv[0] == "hcitool"
    assert "-i" in argv and argv[argv.index("-i") + 1] == "hci2"
    assert "rssi" in argv


def test_btmgmt_no_adapter_omits_flag(mocker):
    _utils._btmgmt_available.clear()
    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="rssi -30\n", stderr="",
    )

    _utils.btmgmt_rssi("AA:BB:CC:DD:EE:FF")
    argv = mock_run.call_args.args[0]
    assert "-i" not in argv


def test_per_adapter_availability_cache_is_isolated(mocker):
    """A missing tool on hci1 must not disable polling for hci0."""
    _utils._hcitool_available.clear()
    mock_run = mocker.patch("subprocess.run", side_effect=FileNotFoundError)

    # hci1 fails and gets disabled
    res, _err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF", adapter="hci1")
    assert res is None
    assert _utils._hcitool_available["hci1"] is False
    # hci0 has not been tried yet — must remain available
    assert "hci0" not in _utils._hcitool_available
    assert _utils._hcitool_available.get("hci0", True) is True

    # Calling hci0 still attempts the subprocess (no short-circuit)
    res, _err = _utils.hcitool_rssi("AA:BB:CC:DD:EE:FF", adapter="hci0")
    assert mock_run.call_count == 2


def test_poll_rssi_forwards_adapter(mocker):
    _utils._btmgmt_available.clear()
    mock_btmgmt = mocker.patch.object(_utils, "btmgmt_rssi", return_value=(-40, ""))
    mock_hcitool = mocker.patch.object(_utils, "hcitool_rssi", return_value=(None, ""))

    rssi, _err, tool = _utils.poll_rssi("AA:BB:CC:DD:EE:FF", "auto", adapter="hci3")
    assert rssi == -40 and tool == "btmgmt"
    assert mock_btmgmt.call_args.kwargs["adapter"] == "hci3"
    mock_hcitool.assert_not_called()
