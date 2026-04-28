"""Command-line RSSI monitor: bluelock_mon <MAC> [--method ...] [--adapter ADDR ...]"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSlot

from bluelock.bluetooth import get_monitor, list_adapters
from bluelock.bluetooth._adapters import AdapterInfo
from bluelock.bluetooth._types import normalize_mac
from bluelock.bluetooth._utils import RSSI_METHODS, btmgmt_rssi, hcitool_rssi

log = logging.getLogger(__name__)


class RssiMonitor(QObject):
    def __init__(self, mac: str, method: str = "auto", adapter_addresses: list[str] | None = None) -> None:
        super().__init__()
        self._mac = normalize_mac(mac)
        self._method = method
        self._adapter_addresses = adapter_addresses or []
        self._monitor = get_monitor()
        self._start_time = time.monotonic()
        self._poll_timer: QTimer | None = None
        self._poll_adapters: list[AdapterInfo] = []

    def start(self) -> None:
        self._monitor.device_appeared.connect(lambda: self._print_row("", "Device appeared"))
        self._monitor.device_disappeared.connect(lambda: self._print_row("", "Device disappeared"))
        self._monitor.error_occurred.connect(lambda msg: print(f"ERROR: {msg}", file=sys.stderr))
        self._monitor.adapter_rssi_updated.connect(self._on_adapter_rssi)

        if self._method == "all":
            self._monitor.rssi_updated.connect(lambda rssi: self._print_row("aggregate", f"{rssi:4} dBm"))
            print(f"Monitoring {self._mac}  (method: all — per-source rows + per-adapter polling)")
            print(f"{'Time':>8}  {'Source':<22}  Result")
            print("-" * 50)
            self._monitor.start_monitoring(self._mac, self._adapter_addresses)
            # The poll-all timer iterates available adapters; capture a snapshot now.
            self._poll_adapters = self._resolve_poll_adapters()
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(2_000)
            self._poll_timer.timeout.connect(self._poll_all)
            self._poll_timer.start()
            self._poll_all()
        else:
            self._monitor.rssi_updated.connect(lambda rssi: self._print_row("aggregate", f"{rssi:4} dBm"))
            print(f"Monitoring {self._mac}  (method: {self._method}, adapters={self._adapter_addresses or 'all'})")
            print(f"{'Time':>8}  {'Source':<22}  RSSI")
            print("-" * 44)
            self._monitor.rssi_method = self._method
            self._monitor.start_monitoring(self._mac, self._adapter_addresses)

    def stop(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
        self._monitor.stop_monitoring()

    def _elapsed(self) -> str:
        s = time.monotonic() - self._start_time
        return f"{s:7.1f}s"

    def _print_row(self, source: str, result: str) -> None:
        print(f"{self._elapsed()}  {source:<22}  {result}")

    def _on_adapter_rssi(self, address: str, rssi: int) -> None:
        self._print_row(f"dbus[{address}]", f"{rssi:4} dBm")

    def _resolve_poll_adapters(self) -> list[AdapterInfo]:
        adapters = [a for a in list_adapters() if a.address and a.powered]
        if self._adapter_addresses:
            wanted = {a for a in (normalize_mac(x) for x in self._adapter_addresses) if a}
            adapters = [a for a in adapters if a.address in wanted]
        return adapters

    @pyqtSlot()
    def _poll_all(self) -> None:
        if not self._poll_adapters:
            # Fall back to the no-adapter form so users without enumerated adapters still see something.
            rssi, err = btmgmt_rssi(self._mac, force=True)
            self._print_row("btmgmt", f"{rssi:4} dBm" if rssi is not None else f"— ({err})")
            rssi, err = hcitool_rssi(self._mac, force=True)
            self._print_row("hcitool", f"{rssi:4} dBm" if rssi is not None else f"— ({err})")
            return
        for ainfo in self._poll_adapters:
            rssi, err = btmgmt_rssi(self._mac, adapter=ainfo.hci_name, force=True)
            self._print_row(f"btmgmt[{ainfo.hci_name}]",
                            f"{rssi:4} dBm" if rssi is not None else f"— ({err})")
            rssi, err = hcitool_rssi(self._mac, adapter=ainfo.hci_name, force=True)
            self._print_row(f"hcitool[{ainfo.hci_name}]",
                            f"{rssi:4} dBm" if rssi is not None else f"— ({err})")


def _print_adapters() -> None:
    """Print the list of currently-known BlueZ adapters, then exit."""
    adapters = list_adapters()
    if not adapters:
        print("No Bluetooth adapters found.")
        return
    print(f"{'hci':<6}  {'BD address':<19}  {'Powered':<8}  Alias")
    print("-" * 60)
    for a in adapters:
        powered = "yes" if a.powered else "no"
        print(f"{a.hci_name:<6}  {a.address:<19}  {powered:<8}  {a.alias}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bluelock_mon",
        description="Monitor Bluetooth RSSI for a device.",
    )
    parser.add_argument("mac", nargs="?", help="Bluetooth MAC address (AA:BB:CC:DD:EE:FF)")
    parser.add_argument("--method", "-m", default="auto",
                        choices=[*RSSI_METHODS, "all"],
                        help="RSSI source: auto (default), dbus, btmgmt, hcitool, or all (show each source)")
    parser.add_argument("--adapter", "-a", action="append", default=[],
                        metavar="BD_ADDR",
                        help="Restrict monitoring to the adapter with this BD address. "
                             "Repeat to use several. Default: all adapters.")
    parser.add_argument("--list-adapters", action="store_true",
                        help="List available Bluetooth adapters and exit.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if args.list_adapters:
        _print_adapters()
        return

    if not args.mac:
        parser.error("the following arguments are required: mac")

    app = QCoreApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sig_timer = QTimer()
    sig_timer.start(200)
    sig_timer.timeout.connect(lambda: None)

    mon = RssiMonitor(args.mac, method=args.method, adapter_addresses=args.adapter)
    mon.start()

    ret = app.exec()
    mon.stop()
    sys.exit(ret)
