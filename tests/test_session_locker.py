"""Tests for bluelock.session_locker."""
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from bluelock.session_locker import SessionLocker, LockError


class TestRunCommand:
    def test_successful_lock_command(self):
        locker = SessionLocker(lock_command="true")
        locker.lock()  # should not raise

    def test_successful_unlock_command(self):
        locker = SessionLocker(unlock_command="true")
        locker.unlock()  # should not raise

    def test_failing_command_raises_lock_error(self):
        locker = SessionLocker(lock_command="false")
        with pytest.raises(LockError, match="exited 1"):
            locker.lock()

    def test_nonexistent_command_raises_lock_error(self):
        locker = SessionLocker(lock_command="definitely_nonexistent_command_xyz")
        with pytest.raises(LockError, match="not found"):
            locker.lock()

    def test_empty_command_raises_lock_error(self):
        locker = SessionLocker(lock_command="")
        # Empty command string means use D-Bus, not empty args
        # Test with whitespace-only string to hit the empty-args branch
        locker2 = SessionLocker.__new__(SessionLocker)
        locker2.lock_command = "   "
        locker2.unlock_command = ""
        with pytest.raises(LockError, match="empty"):
            locker2.lock()

    def test_invalid_shell_syntax_raises_lock_error(self):
        locker = SessionLocker(lock_command="echo 'unclosed")
        with pytest.raises(LockError, match="Cannot parse"):
            locker.lock()

    def test_command_with_args(self):
        locker = SessionLocker(lock_command="echo hello")
        locker.lock()  # echo hello exits 0

    def test_lock_command_stderr_included_in_error(self):
        locker = SessionLocker(lock_command="sh -c 'echo bad >&2; exit 1'")
        with pytest.raises(LockError, match="bad"):
            locker.lock()

    def test_timeout_raises_lock_error(self, mocker):
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sleep", timeout=10))
        locker = SessionLocker(lock_command="sleep 100")
        with pytest.raises(LockError, match="timed out"):
            locker.lock()


class TestDbusLock:
    def _make_mock_bus(self, error=False):
        reply = MagicMock()
        from PyQt6.QtDBus import QDBusMessage
        if error:
            reply.type.return_value = QDBusMessage.MessageType.ErrorMessage
            reply.errorMessage.return_value = "org.freedesktop.DBus.Error.NoReply"
        else:
            reply.type.return_value = QDBusMessage.MessageType.ReplyMessage
        bus = MagicMock()
        bus.call.return_value = reply
        return bus

    def test_dbus_lock_calls_lock_method(self, mocker):
        try:
            from PyQt6.QtDBus import QDBusConnection
        except ImportError:
            pytest.skip("PyQt6.QtDBus not available")
        mock_bus = self._make_mock_bus()
        mocker.patch("PyQt6.QtDBus.QDBusConnection.sessionBus", return_value=mock_bus)
        locker = SessionLocker()
        locker.lock()
        mock_bus.call.assert_called_once()
        msg_arg = mock_bus.call.call_args[0][0]
        assert msg_arg.member() == "Lock"

    def test_dbus_unlock_calls_set_active(self, mocker):
        try:
            from PyQt6.QtDBus import QDBusConnection
        except ImportError:
            pytest.skip("PyQt6.QtDBus not available")
        mock_bus = self._make_mock_bus()
        mocker.patch("PyQt6.QtDBus.QDBusConnection.sessionBus", return_value=mock_bus)
        locker = SessionLocker()
        locker.unlock()
        mock_bus.call.assert_called_once()
        msg_arg = mock_bus.call.call_args[0][0]
        assert msg_arg.member() == "SetActive"

    def test_dbus_error_raises_lock_error(self, mocker):
        try:
            from PyQt6.QtDBus import QDBusConnection
        except ImportError:
            pytest.skip("PyQt6.QtDBus not available")
        mock_bus = self._make_mock_bus(error=True)
        mocker.patch("PyQt6.QtDBus.QDBusConnection.sessionBus", return_value=mock_bus)
        locker = SessionLocker()
        with pytest.raises(LockError, match="D-Bus lock failed"):
            locker.lock()
