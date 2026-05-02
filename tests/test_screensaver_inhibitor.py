"""Tests for bluelock.session_locker.ScreenSaverInhibitor."""
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from bluelock.session_locker import ScreenSaverInhibitor

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def _make_fake_dbus(cookie=12345):
    """Return a fake dbus module whose Inhibit() returns the given cookie value."""
    fake_dbus = ModuleType("dbus")
    fake_dbus.UInt32 = int

    mock_iface = MagicMock()
    mock_iface.Inhibit.return_value = cookie
    mock_iface.UnInhibit.return_value = None

    mock_proxy = MagicMock()
    mock_session_bus = MagicMock()
    mock_session_bus.get_object.return_value = mock_proxy

    fake_dbus.SessionBus = MagicMock(return_value=mock_session_bus)
    fake_dbus.Interface = MagicMock(return_value=mock_iface)

    return fake_dbus, mock_iface


def _subprocess_inhibit_output(cookie=12345):
    """Simulate dbus-send --print-reply output for Inhibit."""
    return f"method return time=1.0 sender=:1.1 -> destination=:1.2 serial=1 reply_serial=2\n   uint32 {cookie}\n"


# --------------------------------------------------------------------------- #
# dbus-python path                                                              #
# --------------------------------------------------------------------------- #

class TestInhibitorDbusPython:
    def setup_method(self):
        # Ensure no stale dbus module from a previous test bleeds through
        sys.modules.pop("dbus", None)

    def teardown_method(self):
        sys.modules.pop("dbus", None)

    def test_inhibit_stores_cookie(self):
        fake_dbus, mock_iface = _make_fake_dbus(cookie=9999)
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()

        assert inh.active
        assert inh._cookie == 9999
        mock_iface.Inhibit.assert_called_once_with("bluelock", "Bluetooth device nearby")

    def test_uninhibit_releases_cookie(self):
        fake_dbus, mock_iface = _make_fake_dbus(cookie=9999)
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()
        inh.uninhibit()

        assert not inh.active
        assert inh._cookie is None
        mock_iface.UnInhibit.assert_called_once_with(9999)

    def test_inhibit_is_idempotent(self):
        fake_dbus, mock_iface = _make_fake_dbus()
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()
        inh.inhibit()

        mock_iface.Inhibit.assert_called_once()

    def test_uninhibit_is_idempotent(self):
        fake_dbus, mock_iface = _make_fake_dbus()
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()
        inh.uninhibit()
        inh.uninhibit()

        mock_iface.UnInhibit.assert_called_once()

    def test_two_cycles(self):
        fake_dbus, mock_iface = _make_fake_dbus(cookie=111)
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()
        inh.uninhibit()
        mock_iface.Inhibit.return_value = 222
        inh.inhibit()
        inh.uninhibit()

        assert mock_iface.Inhibit.call_count == 2
        assert mock_iface.UnInhibit.call_count == 2

    def test_inhibit_dbus_exception_does_not_raise(self):
        fake_dbus, mock_iface = _make_fake_dbus()
        mock_iface.Inhibit.side_effect = Exception("D-Bus gone")
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()   # must not propagate

        assert not inh.active

    def test_uninhibit_dbus_exception_clears_cookie(self):
        fake_dbus, mock_iface = _make_fake_dbus()
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()
        mock_iface.UnInhibit.side_effect = Exception("D-Bus gone")
        inh.uninhibit()   # must not propagate

        assert not inh.active   # cookie cleared in finally block

    def test_uses_dbus_python_when_available(self):
        fake_dbus, _ = _make_fake_dbus()
        sys.modules["dbus"] = fake_dbus

        inh = ScreenSaverInhibitor()
        inh.inhibit()

        assert inh._use_dbus_python is True


# --------------------------------------------------------------------------- #
# dbus-send subprocess fallback path                                            #
# --------------------------------------------------------------------------- #

class TestInhibitorSubprocess:
    def setup_method(self):
        sys.modules.pop("dbus", None)

    def _make_inh(self):
        """Return an inhibitor forced onto the subprocess path."""
        inh = ScreenSaverInhibitor()
        inh._use_dbus_python = False
        return inh

    def test_inhibit_parses_cookie(self):
        result = MagicMock(returncode=0, stdout=_subprocess_inhibit_output(42), stderr="")
        with patch("subprocess.run", return_value=result):
            inh = self._make_inh()
            inh.inhibit()

        assert inh.active
        assert inh._cookie == 42

    def test_uninhibit_passes_uint32(self):
        result_ok = MagicMock(returncode=0, stdout=_subprocess_inhibit_output(42), stderr="")
        result_un = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", side_effect=[result_ok, result_un]) as mock_run:
            inh = self._make_inh()
            inh.inhibit()
            inh.uninhibit()

        uninhibit_call = mock_run.call_args_list[1]
        cmd = uninhibit_call[0][0]
        assert "uint32:42" in cmd

    def test_inhibit_nonzero_returncode_does_not_store_cookie(self):
        result = MagicMock(returncode=1, stdout="", stderr="service unknown")
        with patch("subprocess.run", return_value=result):
            inh = self._make_inh()
            inh.inhibit()

        assert not inh.active

    def test_inhibit_missing_uint32_in_output_warns_and_stores_sentinel(self, caplog):
        result = MagicMock(returncode=0, stdout="method return\n   string unexpected\n", stderr="")
        with patch("subprocess.run", return_value=result):
            inh = self._make_inh()
            with caplog.at_level("WARNING"):
                inh.inhibit()

        # Sentinel 0 is stored so uninhibit() fires and resets state.
        assert inh.active
        assert inh._cookie == 0
        assert "no uint32 cookie" in caplog.text

    def test_inhibit_subprocess_exception_does_not_raise(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("dbus-send not found")):
            inh = self._make_inh()
            inh.inhibit()

        assert not inh.active

    def test_uninhibit_clears_cookie_on_failure(self):
        result_in = MagicMock(returncode=0, stdout=_subprocess_inhibit_output(7), stderr="")
        result_un = MagicMock(returncode=1, stdout="", stderr="no such object")
        with patch("subprocess.run", side_effect=[result_in, result_un]):
            inh = self._make_inh()
            inh.inhibit()
            inh.uninhibit()

        assert not inh.active

    def test_falls_back_to_subprocess_when_dbus_import_fails(self):
        # dbus not in sys.modules and not importable → _use_dbus_python = False
        sys.modules.pop("dbus", None)
        result = MagicMock(returncode=0, stdout=_subprocess_inhibit_output(55), stderr="")
        with patch("subprocess.run", return_value=result), \
             patch.dict(sys.modules, {"dbus": None}):   # None = import will fail
            inh = ScreenSaverInhibitor()
            inh.inhibit()

        assert inh._use_dbus_python is False
        assert inh._cookie == 55
