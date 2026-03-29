"""Application entry point — wires all components together."""
from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from bluelock.bluetooth import get_monitor
from bluelock.config import Config
from bluelock.session_locker import LockError, SessionLocker
from bluelock.signal_processor import SignalProcessor
from bluelock.state_machine import ProximityState, ProximityStateMachine
from bluelock.tray import TrayIcon

log = logging.getLogger(__name__)


class BlueLockApp:
    """Owns all components and connects their signals."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._paused = False
        self._config_dialog = None

        self._config = Config.load()
        self._monitor = get_monitor()
        self._processor = SignalProcessor(self._config.buffer_size)
        self._machine = ProximityStateMachine(
            lock_rssi_threshold=self._config.lock_rssi_threshold,
            lock_duration=self._config.lock_duration,
            unlock_rssi_threshold=self._config.unlock_rssi_threshold,
            unlock_duration=self._config.unlock_duration,
        )
        self._locker = SessionLocker(self._config.lock_command, self._config.unlock_command)
        self._tray = TrayIcon()
        self._device_present = False

        self._eval_timer = QTimer()
        self._eval_timer.setInterval(int(self._config.scan_interval * 1000))
        self._eval_timer.timeout.connect(self._evaluate)

        self._wire_signals()

    def start(self) -> None:
        """Start monitoring and show the tray icon."""
        if self._config.device_mac:
            self._monitor.start_monitoring(self._config.device_mac)
            self._eval_timer.start()
        else:
            log.info("No device configured — opening preferences")
            QTimer.singleShot(0, self._show_preferences)

    def _wire_signals(self) -> None:
        self._monitor.rssi_updated.connect(self._on_rssi_updated)
        self._monitor.device_appeared.connect(self._on_device_appeared)
        self._monitor.device_disappeared.connect(self._on_device_disappeared)
        self._monitor.error_occurred.connect(self._on_monitor_error)

        self._tray.preferences_requested.connect(self._show_preferences)
        self._tray.pause_toggled.connect(self._set_paused)
        self._tray.quit_requested.connect(self._quit)

    # ------------------------------------------------------------------ #
    # Monitoring                                                           #
    # ------------------------------------------------------------------ #

    def _on_rssi_updated(self, rssi: int) -> None:
        self._processor.add_reading(rssi)

    def _on_device_appeared(self) -> None:
        self._device_present = True

    def _on_device_disappeared(self) -> None:
        self._device_present = False
        self._processor.reset()

    def _on_monitor_error(self, message: str) -> None:
        log.warning("Bluetooth monitor error: %s", message)
        self._tray.show_error(message)

    def _evaluate(self) -> None:
        """Called every scan_interval seconds to update state and tray."""
        if self._paused:
            self._tray.update(self._machine.state, self._processor.smoothed_rssi,
                              self._processor.estimated_distance_m,
                              self._config.device_name, paused=True)
            return

        prev_state = self._machine.state
        new_state = self._machine.evaluate(self._processor.smoothed_rssi, self._device_present)

        # Only act on transitions from a known state (not the initial UNKNOWN→* transition)
        if new_state is not None and prev_state != ProximityState.UNKNOWN:
            if new_state == ProximityState.GONE:
                self._do_lock()
            elif new_state == ProximityState.ACTIVE:
                self._do_unlock()

        self._tray.update(self._machine.state, self._processor.smoothed_rssi,
                          self._processor.estimated_distance_m,
                          self._config.device_name, paused=False,
                          lock_pending=self._machine.lock_pending)

    def _do_lock(self) -> None:
        try:
            self._locker.lock()
            log.info("Session locked")
        except LockError as exc:
            log.error("Lock failed: %s", exc)
            self._tray.show_error(str(exc))

    def _do_unlock(self) -> None:
        try:
            self._locker.unlock()
            log.info("Session unlocked")
        except LockError as exc:
            log.error("Unlock failed: %s", exc)
            self._tray.show_error(str(exc))

    # ------------------------------------------------------------------ #
    # Tray menu actions                                                    #
    # ------------------------------------------------------------------ #

    def _set_paused(self, paused: bool) -> None:
        self._paused = paused
        log.info("Monitoring %s", "paused" if paused else "resumed")

    def _show_preferences(self) -> None:
        from bluelock.config_dialog import ConfigDialog
        if self._config_dialog is not None:
            self._config_dialog.reject()
            return

        dlg = ConfigDialog(self._config)
        dlg.connect_monitor(self._monitor)
        self._config_dialog = dlg

        # Start a scan so the device list populates while the dialog is open
        self._monitor.start_scan()

        if dlg.exec():
            self._apply_config(dlg.current_config())

        self._monitor.stop_scan()
        self._config_dialog = None

    def _apply_config(self, new_cfg: Config) -> None:
        """Apply a new configuration, saving it and restarting monitoring."""
        self._config = new_cfg
        new_cfg.save()

        self._locker.lock_command = new_cfg.lock_command
        self._locker.unlock_command = new_cfg.unlock_command
        self._processor.buffer_size = new_cfg.buffer_size
        self._machine = ProximityStateMachine(
            lock_rssi_threshold=new_cfg.lock_rssi_threshold,
            lock_duration=new_cfg.lock_duration,
            unlock_rssi_threshold=new_cfg.unlock_rssi_threshold,
            unlock_duration=new_cfg.unlock_duration,
        )
        self._eval_timer.setInterval(int(new_cfg.scan_interval * 1000))

        self._monitor.stop_monitoring()
        self._device_present = False
        self._processor.reset()

        if new_cfg.device_mac:
            self._monitor.start_monitoring(new_cfg.device_mac)
            self._eval_timer.start()

    def _quit(self) -> None:
        self._eval_timer.stop()
        self._monitor.stop_monitoring()
        self._app.quit()


def main() -> None:
    """Application entry point."""
    import signal
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv)
    app.setApplicationName("BlueLock")
    app.setQuitOnLastWindowClosed(False)   # keep running after dialogs close

    # Qt's C++ event loop never yields to Python, so SIGINT would be ignored.
    # Install a handler that calls quit(), and a timer that wakes Python periodically
    # so the signal is actually delivered.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.start(200)
    sig_timer.timeout.connect(lambda: None)

    bluelock = BlueLockApp(app)
    bluelock.start()

    sys.exit(app.exec())
