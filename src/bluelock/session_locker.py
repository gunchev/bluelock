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
        """Unlock via org.freedesktop.login1.Session.Unlock() on the system bus.

        SetActive(false) on org.freedesktop.ScreenSaver only dismisses the
        screensaver, not a password-locked session.  login1 Session.Unlock()
        is what 'loginctl unlock-session' uses and works on KDE/GNOME/etc.
        """
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusMessage
            import os

            bus = QDBusConnection.systemBus()

            # 1. Get the session path for our current PID.
            # This is more robust than relying on $XDG_SESSION_ID.
            manager_msg = QDBusMessage.createMethodCall(
                "org.freedesktop.login1", "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager", "GetSessionByPID")
            manager_msg.setArguments([os.getpid()])
            manager_reply = bus.call(manager_msg)

            if manager_reply.type() == QDBusMessage.MessageType.ErrorMessage:
                # Fallback to $XDG_SESSION_ID if GetSessionByPID fails
                session_id = os.environ.get("XDG_SESSION_ID")
                if not session_id:
                    raise LockError(f"D-Bus unlock failed: {manager_reply.errorMessage()} "
                                   f"(and XDG_SESSION_ID is not set)")
                session_path = f"/org/freedesktop/login1/session/{session_id}"
                log.debug("GetSessionByPID failed, falling back to XDG_SESSION_ID=%s", session_id)
            else:
                session_path = manager_reply.arguments()[0]

            # 2. Call Unlock() on the session object.
            msg = QDBusMessage.createMethodCall(
                "org.freedesktop.login1", session_path,
                "org.freedesktop.login1.Session", "Unlock")
            reply = bus.call(msg)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise LockError(f"D-Bus unlock failed: {reply.errorMessage()}")
            log.info("Session unlocked via login1 D-Bus (%s)", session_path)
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


class ScreenSaverInhibitor:
    """Prevents the screensaver / idle-lock while a Bluetooth device is nearby.

    Calls org.freedesktop.ScreenSaver.Inhibit on the session bus and holds the
    returned cookie until uninhibit() is called.  Safe to call multiple times.
    """

    _APP_NAME = "BlueLock"
    _REASON = "Bluetooth device is nearby"

    def __init__(self) -> None:
        self._cookie: int | None = None

    @property
    def active(self) -> bool:
        return self._cookie is not None

    def inhibit(self) -> None:
        """Acquire an inhibit lock (no-op if already held)."""
        if self._cookie is not None:
            return
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusMessage
            bus = QDBusConnection.sessionBus()
            msg = QDBusMessage.createMethodCall(_SS_SVC, _SS_PATH, _SS_SVC, "Inhibit")
            msg.setArguments([self._APP_NAME, self._REASON])
            reply = bus.call(msg)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                log.warning("ScreenSaver.Inhibit failed: %s", reply.errorMessage())
                return
            args = reply.arguments()
            self._cookie = int(args[0]) if args else None
            log.info("Screensaver inhibited (cookie=%s)", self._cookie)
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.Inhibit error: %s", exc)

    def uninhibit(self) -> None:
        """Release the inhibit lock (no-op if not held)."""
        if self._cookie is None:
            return
        try:
            from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage
            bus = QDBusConnection.sessionBus()
            # Use QDBusInterface so Qt introspects the remote object and coerces
            # the Python int cookie to the declared uint32 ('u') type — passing it
            # via QDBusMessage.setArguments sends int32 ('i') which KDE rejects.
            iface = QDBusInterface(_SS_SVC, _SS_PATH, _SS_SVC, bus)
            reply = iface.call("UnInhibit", self._cookie)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                log.warning("ScreenSaver.UnInhibit failed: %s", reply.errorMessage())
            else:
                log.info("Screensaver uninhibited (cookie=%s)", self._cookie)
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.UnInhibit error: %s", exc)
        finally:
            self._cookie = None
