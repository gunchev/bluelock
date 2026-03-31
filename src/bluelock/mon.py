"""Command-line RSSI monitor: bluelock_mon <MAC> [--method auto|btmgmt|hcitool|all]"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSlot

from bluelock.bluetooth import get_monitor
from bluelock.bluetooth._types import normalize_mac
from bluelock.bluetooth._utils import RSSI_METHODS, btmgmt_rssi, hcitool_rssi

log = logging.getLogger(__name__)


class RssiMonitor(QObject):
    def __init__(self, mac: str, method: str = "auto") -> None:
        super().__init__()
        self._mac = normalize_mac(mac)
        self._method = method
        self._monitor = get_monitor()
        self._start_time = time.monotonic()
        self._poll_timer: QTimer | None = None

    def start(self) -> None:
        self._monitor.device_appeared.connect(lambda: self._print_row("", "Device appeared"))
        self._monitor.device_disappeared.connect(lambda: self._print_row("", "Device disappeared"))
        self._monitor.error_occurred.connect(lambda msg: print(f"ERROR: {msg}", file=sys.stderr))

        if self._method == "all":
            self._monitor.rssi_updated.connect(lambda rssi: self._print_row("D-Bus / poll", f"{rssi:4} dBm"))
            print(f"Monitoring {self._mac}  (method: all — showing each source independently)")
            print(f"{'Time':>8}  {'Source':<18}  Result")
            print("-" * 46)
            self._monitor.start_monitoring(self._mac)
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(2_000)
            self._poll_timer.timeout.connect(self._poll_all)
            self._poll_timer.start()
            self._poll_all()   # immediate first sample
        else:
            self._monitor.rssi_updated.connect(lambda rssi: self._print_row("RSSI", f"{rssi:4} dBm"))
            print(f"Monitoring {self._mac}  (method: {self._method})")
            print(f"{'Time':>8}  {'Source':<14}  RSSI")
            print("-" * 36)
            self._monitor.rssi_method = self._method
            self._monitor.start_monitoring(self._mac)

    def stop(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
        self._monitor.stop_monitoring()

    def _elapsed(self) -> str:
        s = time.monotonic() - self._start_time
        return f"{s:7.1f}s"

    def _print_row(self, source: str, result: str) -> None:
        print(f"{self._elapsed()}  {source:<18}  {result}")

    @pyqtSlot()
    def _poll_all(self) -> None:
        rssi, err = btmgmt_rssi(self._mac, force=True)
        self._print_row("btmgmt", f"{rssi:4} dBm" if rssi is not None else f"— ({err})")

        rssi, err = hcitool_rssi(self._mac, force=True)
        self._print_row("hcitool", f"{rssi:4} dBm" if rssi is not None else f"— ({err})")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bluelock_mon",
        description="Monitor Bluetooth RSSI for a device.",
    )
    parser.add_argument("mac", help="Bluetooth MAC address (AA:BB:CC:DD:EE:FF)")
    parser.add_argument("--method", "-m", default="auto",
                        choices=[*RSSI_METHODS, "all"],
                        help="RSSI source: auto (default), dbus, btmgmt, hcitool, or all (show each source)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    app = QCoreApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.start(200)
    sig_timer.timeout.connect(lambda: None)

    mon = RssiMonitor(args.mac, method=args.method)
    mon.start()

    ret = app.exec()
    mon.stop()
    sys.exit(ret)
