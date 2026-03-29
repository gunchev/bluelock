"""System tray icon with context menu."""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from bluelock.state_machine import ProximityState

log = logging.getLogger(__name__)

_ICONS_DIR = Path(__file__).parent.parent.parent / "resources" / "icons"

_ICON_FILES: dict[str, str] = {
    "close":  "bluelock_close.svg",
    "far":    "bluelock_far.svg",
    "gone":   "bluelock_gone.svg",
    "error":  "bluelock_error.svg",
    "paused": "bluelock_paused.svg",
}


def _load_icons() -> dict[str, QIcon]:
    icons = {}
    for key, filename in _ICON_FILES.items():
        path = _ICONS_DIR / filename
        if path.exists():
            icons[key] = QIcon(str(path))
        else:
            log.warning("Icon not found: %s", path)
            icons[key] = QIcon()  # blank fallback
    return icons


class TrayIcon(QObject):
    """System tray icon that reflects the current proximity state.

    Signals:
        preferences_requested: user clicked Preferences
        pause_toggled(bool): user toggled Pause (True = pausing)
        quit_requested: user clicked Quit
    """

    preferences_requested = pyqtSignal()
    pause_toggled = pyqtSignal(bool)
    quit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._icons = _load_icons()
        self._paused = False
        self._tray = QSystemTrayIcon(self._icons["error"])
        self._build_menu()
        self._tray.setVisible(True)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def update(self, state: ProximityState, rssi: float, distance_m: float,
               device_name: str, paused: bool) -> None:
        """Update the icon and tooltip to reflect the current state."""
        self._paused = paused
        self._pause_action.setChecked(paused)

        icon_key = self._icon_key(state, paused)
        self._tray.setIcon(self._icons[icon_key])
        self._tray.setToolTip(self._build_tooltip(state, rssi, distance_m, device_name, paused))

    def show_error(self, message: str) -> None:
        """Display error icon and message in tooltip."""
        self._tray.setIcon(self._icons["error"])
        self._tray.setToolTip(f"BlueLock error: {message}")

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._pause_action.setChecked(paused)

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _build_menu(self) -> None:
        menu = QMenu()

        act_prefs = menu.addAction("Preferences…")
        act_prefs.triggered.connect(self.preferences_requested)

        self._pause_action = menu.addAction("Pause")
        self._pause_action.setCheckable(True)
        self._pause_action.toggled.connect(self.pause_toggled)

        menu.addSeparator()

        act_about = menu.addAction("About BlueLock")
        act_about.triggered.connect(self._on_about)

        menu.addSeparator()

        act_quit = menu.addAction("Quit")
        act_quit.triggered.connect(self.quit_requested)

        self._tray.setContextMenu(menu)

    def _on_about(self) -> None:
        from bluelock.about_dialog import AboutDialog
        dlg = AboutDialog()
        dlg.exec()

    @staticmethod
    def _icon_key(state: ProximityState, paused: bool) -> str:
        if paused:
            return "paused"
        return {
            ProximityState.ACTIVE:  "close",
            ProximityState.GONE:    "gone",
            ProximityState.UNKNOWN: "error",
        }.get(state, "error")

    @staticmethod
    def _build_tooltip(state: ProximityState, rssi: float, distance_m: float,
                       device_name: str, paused: bool) -> str:
        label = device_name or "No device"
        if paused:
            return f"BlueLock — Paused\n{label}"
        state_str = {
            ProximityState.ACTIVE:  "Unlocked",
            ProximityState.GONE:    "Locked",
            ProximityState.UNKNOWN: "Initialising…",
        }.get(state, "Unknown")
        rssi_str = f"{rssi:.0f} dBm" if rssi > -127 else "—"
        dist_str = f"{distance_m:.1f} m" if distance_m < 999 else "out of range"
        return f"BlueLock — {state_str}\n{label}\nRSSI: {rssi_str}  Distance: ≈{dist_str}"
