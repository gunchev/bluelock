"""Session lock/unlock via D-Bus ScreenSaver API or user-configured commands."""
from __future__ import annotations

import logging
import shlex
import subprocess

log = logging.getLogger(__name__)

# D-Bus constants for org.freedesktop.ScreenSaver
_SS_SVC = "org.freedesktop.ScreenSaver"
_SS_PATH = "/ScreenSaver"
_SS_APP = "bluelock"
_SS_REASON = "Bluetooth device nearby"


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
    """Inhibits the screensaver / idle-lock while a Bluetooth device is nearby.

    Uses dbus-python (python3-dbus) if available — it returns dbus.UInt32 from
    Inhibit so the cookie round-trips correctly in UnInhibit.

    Falls back to dbus-send subprocess when dbus-python is not installed.

    PyQt6.QtDBus cannot be used: it serialises Python int as D-Bus int32 ('i'),
    but KDE's UnInhibit expects uint32 ('u') and rejects the call with
    "No such method 'UnInhibit' (signature 'i')".
    """

    def __init__(self) -> None:
        self._cookie = None           # dbus.UInt32 (dbus-python) or int (subprocess)
        self._use_dbus_python: bool | None = None   # None = not yet probed

    @property
    def active(self) -> bool:
        return self._cookie is not None

    def inhibit(self) -> None:
        """Inhibit the screensaver (no-op if already active)."""
        if self._cookie is not None:
            return
        if self._use_dbus_python is None:
            try:
                import dbus as _dbus  # noqa: F401
                self._use_dbus_python = True
                log.debug("ScreenSaverInhibitor: using dbus-python")
            except ImportError:
                self._use_dbus_python = False
                log.debug("ScreenSaverInhibitor: dbus-python not available, using dbus-send")
        if self._use_dbus_python:
            self._inhibit_dbus_python()
        else:
            self._inhibit_subprocess()

    def uninhibit(self) -> None:
        """Release the screensaver inhibition (no-op if not active)."""
        if self._cookie is None:
            return
        if self._use_dbus_python:
            self._uninhibit_dbus_python()
        else:
            self._uninhibit_subprocess()

    # ------------------------------------------------------------------ #
    # dbus-python implementation                                           #
    # ------------------------------------------------------------------ #

    def _inhibit_dbus_python(self) -> None:
        try:
            import dbus
            bus = dbus.SessionBus()
            iface = dbus.Interface(bus.get_object(_SS_SVC, _SS_PATH), _SS_SVC)
            self._cookie = iface.Inhibit(_SS_APP, _SS_REASON)  # returns dbus.UInt32
            log.info("Screensaver inhibited via dbus-python (cookie=%s)", self._cookie)
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.Inhibit (dbus-python) failed: %s", exc)

    def _uninhibit_dbus_python(self) -> None:
        try:
            import dbus
            bus = dbus.SessionBus()
            iface = dbus.Interface(bus.get_object(_SS_SVC, _SS_PATH), _SS_SVC)
            iface.UnInhibit(self._cookie)   # cookie is dbus.UInt32 — correct type
            log.info("Screensaver uninhibited via dbus-python (cookie=%s)", self._cookie)
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.UnInhibit (dbus-python) failed: %s", exc)
        finally:
            self._cookie = None

    # ------------------------------------------------------------------ #
    # dbus-send subprocess fallback                                        #
    # ------------------------------------------------------------------ #

    def _inhibit_subprocess(self) -> None:
        try:
            result = subprocess.run(
                ["dbus-send", "--session", "--print-reply", f"--dest={_SS_SVC}", _SS_PATH,
                 f"{_SS_SVC}.Inhibit", f"string:{_SS_APP}", f"string:{_SS_REASON}"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[0] == "uint32":
                        self._cookie = int(parts[1])
                        log.info("Screensaver inhibited via dbus-send (cookie=%s)", self._cookie)
                        return
            log.warning("ScreenSaver.Inhibit (dbus-send) failed: %s", result.stderr.strip())
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.Inhibit (dbus-send) error: %s", exc)

    def _uninhibit_subprocess(self) -> None:
        try:
            result = subprocess.run(
                ["dbus-send", "--session", "--print-reply", f"--dest={_SS_SVC}", _SS_PATH,
                 f"{_SS_SVC}.UnInhibit", f"uint32:{self._cookie}"],
                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                log.info("Screensaver uninhibited via dbus-send (cookie=%s)", self._cookie)
            else:
                log.warning("ScreenSaver.UnInhibit (dbus-send) failed: %s", result.stderr.strip())
        except Exception as exc:  # noqa: BLE001
            log.warning("ScreenSaver.UnInhibit (dbus-send) error: %s", exc)
        finally:
            self._cookie = None
