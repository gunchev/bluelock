"""Session lock/unlock via D-Bus ScreenSaver API or user-configured commands."""
from __future__ import annotations

import logging
import shlex
import subprocess

log = logging.getLogger(__name__)

# D-Bus constants for org.freedesktop.ScreenSaver
_SS_SVC = "org.freedesktop.ScreenSaver"
_SS_PATH = "/ScreenSaver"


class LockError(Exception):
    """Raised when a lock or unlock action fails."""


class SessionLocker:
    """Locks and unlocks the desktop session.

    Uses D-Bus org.freedesktop.ScreenSaver by default.
    Falls back to user-configured shell commands (executed safely without shell=True).
    """

    def __init__(self, lock_command: str = "", unlock_command: str = "") -> None:
        self.lock_command = lock_command
        self.unlock_command = unlock_command

    def lock(self) -> None:
        """Lock the session.

        Raises:
            LockError: if the lock operation fails.
        """
        if self.lock_command:
            self._run_command(self.lock_command, "lock")
        else:
            self._dbus_lock()

    def unlock(self) -> None:
        """Unlock the session.

        Raises:
            LockError: if the unlock operation fails.
        """
        if self.unlock_command:
            self._run_command(self.unlock_command, "unlock")
        else:
            self._dbus_unlock()

    def _dbus_lock(self) -> None:
        """Lock via D-Bus org.freedesktop.ScreenSaver.Lock()."""
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusMessage
            bus = QDBusConnection.sessionBus()
            msg = QDBusMessage.createMethodCall(_SS_SVC, _SS_PATH, _SS_SVC, "Lock")
            reply = bus.call(msg)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise LockError(f"D-Bus lock failed: {reply.errorMessage()}")
            log.info("Session locked via D-Bus")
        except ImportError as exc:
            raise LockError("PyQt6.QtDBus not available") from exc

    def _dbus_unlock(self) -> None:
        """Unlock via D-Bus org.freedesktop.ScreenSaver.SetActive(false)."""
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusMessage
            bus = QDBusConnection.sessionBus()
            msg = QDBusMessage.createMethodCall(_SS_SVC, _SS_PATH, _SS_SVC, "SetActive")
            msg.setArguments([False])
            reply = bus.call(msg)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise LockError(f"D-Bus unlock failed: {reply.errorMessage()}")
            log.info("Session unlocked via D-Bus")
        except ImportError as exc:
            raise LockError("PyQt6.QtDBus not available") from exc

    @staticmethod
    def _run_command(command: str, action: str) -> None:
        """Run a user-configured command safely (no shell=True)."""
        try:
            args = shlex.split(command)
        except ValueError as exc:
            raise LockError(f"Cannot parse {action} command {command!r}: {exc}") from exc

        if not args:
            raise LockError(f"{action.capitalize()} command is empty")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except FileNotFoundError as exc:
            raise LockError(f"{action.capitalize()} command not found: {args[0]!r}") from exc
        except subprocess.TimeoutExpired as exc:
            raise LockError(f"{action.capitalize()} command timed out: {command!r}") from exc
        except OSError as exc:
            raise LockError(f"{action.capitalize()} command failed: {exc}") from exc

        if result.returncode != 0:
            detail = f": {result.stderr.strip()}" if result.stderr.strip() else ""
            raise LockError(f"{action.capitalize()} command exited {result.returncode}{detail}")
        log.info("Session %sed via command: %s", action, command)
