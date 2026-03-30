"""Command-line RSSI monitor: bluelock_mon <MAC>"""
from __future__ import annotations

import logging
import signal
import sys
import time

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from bluelock.bluetooth import get_monitor
from bluelock.bluetooth._types import normalize_mac

log = logging.getLogger(__name__)


class RssiMonitor(QObject):
    def __init__(self, mac: str) -> None:
        super().__init__()
        self._mac = normalize_mac(mac)
        self._monitor = get_monitor()
        self._start_time = time.monotonic()

    def start(self) -> None:
        self._monitor.rssi_updated.connect(self._on_rssi_updated)
        self._monitor.device_appeared.connect(lambda: print(f"{self._elapsed()}  Device appeared"))
        self._monitor.device_disappeared.connect(lambda: print(f"{self._elapsed()}  Device disappeared"))
        self._monitor.error_occurred.connect(lambda msg: print(f"ERROR: {msg}", file=sys.stderr))

        print(f"Monitoring {self._mac}")
        print(f"{'Time':>8}  {'Source':<14}  RSSI")
        print("-" * 36)

        self._monitor.start_monitoring(self._mac)

    def stop(self) -> None:
        self._monitor.stop_monitoring()

    def _elapsed(self) -> str:
        s = time.monotonic() - self._start_time
        return f"{s:7.1f}s"

    @pyqtSlot(int)
    def _on_rssi_updated(self, rssi: int) -> None:
        print(f"{self._elapsed()}  {'RSSI':<14}  {rssi:4} dBm")



def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <MAC>", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.WARNING)

    app = QCoreApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.start(200)
    sig_timer.timeout.connect(lambda: None)

    mon = RssiMonitor(sys.argv[1])
    mon.start()

    ret = app.exec()
    mon.stop()
    sys.exit(ret)
