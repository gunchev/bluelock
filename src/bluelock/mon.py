"""Command-line RSSI monitor: bluelock_mon <MAC>"""
from __future__ import annotations

import logging
import signal
import sys
import time

from PyQt6.QtCore import QCoreApplication, QObject, QTimer, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from bluelock.bluetooth._types import DeviceInfo, mac_to_dbus_path, normalize_mac
from bluelock.bluetooth._utils import btmgmt_rssi, hcitool_rssi

log = logging.getLogger(__name__)

_BLUEZ_SVC = "org.bluez"
_BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
_BLUEZ_DEVICE_IFACE = "org.bluez.Device1"
_DBUS_OBJMGR_IFACE = "org.freedesktop.DBus.ObjectManager"
_DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"
_DEFAULT_ADAPTER = "/org/bluez/hci0"

_POLL_MS = 1_000   # poll interval for direct property read


class RssiMonitor(QObject):
    def __init__(self, mac: str) -> None:
        super().__init__()
        self._mac = normalize_mac(mac)
        self._path = mac_to_dbus_path(_DEFAULT_ADAPTER, self._mac)
        self._bus = QDBusConnection.systemBus()
        self._start_time = time.monotonic()

        self._timer = QTimer()
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        if not self._bus.isConnected():
            print("ERROR: cannot connect to D-Bus system bus", file=sys.stderr)
            QCoreApplication.exit(1)
            return

        # Connect ObjectManager signals to catch device appearances
        self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded", self._on_interfaces_added)

        # Connect PropertiesChanged on the device object
        ok = self._bus.connect(_BLUEZ_SVC, self._path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_props_changed)
        print(f"Monitoring {self._mac}  path={self._path}  PropertiesChanged connected={ok}")
        print(f"{'Time':>8}  {'Source':<14}  RSSI")
        print("-" * 36)

        # Start discovery so BlueZ emits RSSI updates
        adapter = QDBusInterface(_BLUEZ_SVC, _DEFAULT_ADAPTER, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StartDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            err = reply.errorMessage()
            if "InProgress" not in err:
                print(f"WARNING: StartDiscovery: {err}", file=sys.stderr)

        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        adapter = QDBusInterface(_BLUEZ_SVC, _DEFAULT_ADAPTER, _BLUEZ_ADAPTER_IFACE, self._bus)
        adapter.call("StopDiscovery")

    def _elapsed(self) -> str:
        s = time.monotonic() - self._start_time
        return f"{s:7.1f}s"

    @pyqtSlot('QDBusMessage')
    def _on_props_changed(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if not args or str(args[0]) != _BLUEZ_DEVICE_IFACE:
            return
        changed = args[1] if len(args) > 1 else {}
        if not isinstance(changed, dict):
            print(f"{self._elapsed()}  {'PropsChanged':<14}  [args[1] type={type(changed).__name__}]")
            return
        if "RSSI" in changed:
            print(f"{self._elapsed()}  {'PropsChanged':<14}  {changed['RSSI']:4} dBm")
        elif changed:
            print(f"{self._elapsed()}  {'PropsChanged':<14}  (keys: {', '.join(changed.keys())})")

    @pyqtSlot('QDBusMessage')
    def _on_interfaces_added(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if len(args) < 2:
            return
        path = str(args[0])
        interfaces = args[1]
        if not isinstance(interfaces, dict) or _BLUEZ_DEVICE_IFACE not in interfaces:
            return
        props = interfaces[_BLUEZ_DEVICE_IFACE]
        mac = normalize_mac(props.get("Address", ""))
        if mac != self._mac:
            return
        rssi = props.get("RSSI")
        rssi_str = f"{rssi:4} dBm" if rssi is not None else "  no RSSI"
        print(f"{self._elapsed()}  {'InterfAdded':<14}  {rssi_str}")
        # Re-connect PropertiesChanged to the actual path in case it differs
        if path != self._path:
            self._bus.disconnect(_BLUEZ_SVC, self._path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_props_changed)
            self._path = path
            ok = self._bus.connect(_BLUEZ_SVC, self._path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_props_changed)
            print(f"{self._elapsed()}  {'re-connect':<14}  path={path}  ok={ok}")

    def _tick(self) -> None:
        """Poll RSSI every second."""
        t = self._elapsed()
        rssi, err = btmgmt_rssi(self._mac)
        if rssi is not None:
            print(f"{t}  {'btmgmt':<14}  {rssi:4} dBm")
            return
        print(f"{t}  {'btmgmt':<14}  {err}")
        rssi, err = hcitool_rssi(self._mac)
        if rssi is not None:
            print(f"{t}  {'hcitool':<14}  {rssi:4} dBm")
        else:
            print(f"{t}  {'hcitool':<14}  {err}")



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
