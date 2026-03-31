"""BlueZ D-Bus Bluetooth monitor using PyQt6.QtDBus."""
from __future__ import annotations

import logging
import subprocess
import time

from PyQt6.QtCore import QTimer, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from bluelock.bluetooth._base import AbstractBluetoothMonitor
from bluelock.bluetooth._types import DeviceInfo, mac_to_dbus_path, normalize_mac
from bluelock.bluetooth._utils import poll_rssi

log = logging.getLogger(__name__)

_BLUEZ_SVC = "org.bluez"
_BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
_BLUEZ_DEVICE_IFACE = "org.bluez.Device1"
_DBUS_OBJMGR_IFACE = "org.freedesktop.DBus.ObjectManager"
_DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"
_DEFAULT_ADAPTER = "/org/bluez/hci0"

# Poll interval for hcitool RSSI fallback (classic BT devices don't emit PropertiesChanged RSSI)
_RSSI_POLL_MS = 2_000


class BluezDBusMonitor(AbstractBluetoothMonitor):
    """Monitors Bluetooth device proximity via BlueZ D-Bus signals.

    Primary method: subscribe to PropertiesChanged on org.bluez.Device1.
    BlueZ emits RSSI property updates during active discovery.

    Fallback: for connected classic BT devices where BlueZ does not emit RSSI
    via D-Bus, poll 'hcitool rssi <mac>' on a timer.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._bus = QDBusConnection.systemBus()
        self._adapter_path = _DEFAULT_ADAPTER
        self._target_mac = ""
        self._target_path = ""
        self._monitoring = False
        self._scanning = False
        self._last_rssi_time = 0.0
        self._poll_reachable = False   # True when btmgmt/hcitool last succeeded
        self._using_poll = False
        self._poll_tool = ""
        self._rssi_method = "auto"

        # Timer for hcitool RSSI polling (classic BT devices don't emit RSSI via PropertiesChanged)
        self._stale_timer = QTimer(self)
        self._stale_timer.setInterval(_RSSI_POLL_MS)
        self._stale_timer.timeout.connect(self._on_stale_check)

        # Timer to end a scan automatically
        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.timeout.connect(self.stop_scan)

        if not self._bus.isConnected():
            log.error("Cannot connect to D-Bus system bus")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start_monitoring(self, mac: str) -> None:
        """Begin RSSI monitoring for the given MAC address."""
        mac = normalize_mac(mac)
        if not mac:
            self.error_occurred.emit(f"Invalid MAC address: {mac!r}")
            return

        if self._monitoring:
            self.stop_monitoring()

        self._target_mac = mac
        self._target_path = mac_to_dbus_path(self._adapter_path, mac)
        self._monitoring = True
        self._last_rssi_time = 0.0
        self._poll_reachable = False
        log.info("Starting monitoring for %s (%s)", mac, self._target_path)

        self._connect_object_manager_signals()
        self._connect_device_signals(self._target_path)
        self._start_discovery()
        self._stale_timer.start()

    def stop_monitoring(self) -> None:
        """Stop RSSI monitoring."""
        if not self._monitoring:
            return
        log.info("Stopping monitoring for %s", self._target_mac)
        self._stale_timer.stop()
        self._stop_discovery()
        self._disconnect_device_signals(self._target_path)
        self._disconnect_object_manager_signals()
        self._monitoring = False
        self._poll_reachable = False
        self._target_mac = ""
        self._target_path = ""

    def start_scan(self, timeout_ms: int = 10_000) -> None:
        """Scan for nearby Bluetooth devices."""
        if self._scanning:
            return
        log.info("Starting device scan (timeout=%dms)", timeout_ms)
        self._scanning = True
        self._connect_object_manager_signals()
        self._start_discovery()
        self._scan_timer.start(timeout_ms)
        # Emit already-known devices immediately; InterfacesAdded won't fire for them
        for device in self.get_known_devices():
            self.scan_result.emit(device)

    def stop_scan(self) -> None:
        """Stop an in-progress scan."""
        if not self._scanning:
            return
        log.info("Stopping device scan")
        self._scan_timer.stop()
        if not self._monitoring:
            self._stop_discovery()
            self._disconnect_object_manager_signals()
        self._scanning = False
        self.scan_finished.emit()

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    @property
    def rssi_method(self) -> str:
        return self._rssi_method

    @rssi_method.setter
    def rssi_method(self, value: str) -> None:
        self._rssi_method = value

    # ------------------------------------------------------------------ #
    # D-Bus signal connections                                             #
    # ------------------------------------------------------------------ #

    def _connect_object_manager_signals(self) -> None:
        ok1 = self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded", self._on_interfaces_added)
        ok2 = self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesRemoved", self._on_interfaces_removed)
        log.debug("ObjectManager signals connected: added=%s removed=%s", ok1, ok2)

    def _disconnect_object_manager_signals(self) -> None:
        self._bus.disconnect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded", self._on_interfaces_added)
        self._bus.disconnect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesRemoved", self._on_interfaces_removed)

    def _connect_device_signals(self, path: str) -> None:
        ok = self._bus.connect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_properties_changed)
        if not ok:
            log.warning("Failed to connect PropertiesChanged for %s: %s", path, self._bus.lastError().message())

    def _disconnect_device_signals(self, path: str) -> None:
        self._bus.disconnect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_properties_changed)

    # ------------------------------------------------------------------ #
    # BlueZ adapter control                                                #
    # ------------------------------------------------------------------ #

    def _start_discovery(self) -> None:
        adapter = QDBusInterface(_BLUEZ_SVC, self._adapter_path, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StartDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            err = reply.errorMessage()
            if "InProgress" not in err:
                log.warning("StartDiscovery failed: %s", err)
                self.error_occurred.emit(f"Bluetooth discovery error: {err}")
            else:
                log.debug("StartDiscovery: Operation already in progress")

    def _stop_discovery(self) -> None:
        adapter = QDBusInterface(_BLUEZ_SVC, self._adapter_path, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StopDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            log.debug("StopDiscovery: %s", reply.errorMessage())

    # ------------------------------------------------------------------ #
    # D-Bus signal handlers                                                #
    # ------------------------------------------------------------------ #

    @pyqtSlot('QDBusMessage')
    def _on_properties_changed(self, msg: QDBusMessage) -> None:
        """Handle PropertiesChanged on a BlueZ device object."""
        args = msg.arguments()
        if not args:
            return
        iface = str(args[0])
        log.debug("PropertiesChanged iface=%s keys=%s", iface,
                  list(args[1].keys()) if len(args) > 1 and isinstance(args[1], dict) else args[1:])
        if iface != _BLUEZ_DEVICE_IFACE:
            return
        changed = args[1] if len(args) > 1 else {}
        if "RSSI" in changed:
            rssi = changed["RSSI"]
            if self._using_poll:
                log.info("Switching to D-Bus RSSI updates for %s", self._target_mac)
                self._using_poll = False
                self._poll_tool = ""
            log.debug("RSSI update from D-Bus: %d dBm", rssi)
            self._last_rssi_time = time.monotonic()
            self.rssi_updated.emit(int(rssi))
        if "Connected" in changed:
            connected = bool(changed["Connected"])
            log.info("Device %s: Connected=%s", self._target_mac, connected)
            if connected:
                self._poll_reachable = True
                self.device_appeared.emit()
            else:
                self._poll_reachable = False
                self.device_disappeared.emit()

    @pyqtSlot('QDBusMessage')
    def _on_interfaces_added(self, msg: QDBusMessage) -> None:
        """Handle a new BlueZ object appearing (device found during scan)."""
        args = msg.arguments()
        if len(args) < 2:
            return
        path = str(args[0])
        interfaces = args[1]
        if _BLUEZ_DEVICE_IFACE not in interfaces:
            return
        props = interfaces[_BLUEZ_DEVICE_IFACE]
        mac = normalize_mac(props.get("Address", ""))
        name = str(props.get("Name", ""))
        rssi = props.get("RSSI")
        if not mac:
            return

        if self._scanning:
            self.scan_result.emit(DeviceInfo(mac=mac, name=name, rssi=rssi))

        if self._monitoring and mac == self._target_mac:
            log.info("Target device appeared: %s", mac)
            self._connect_device_signals(path)
            self.device_appeared.emit()
            if rssi is not None:
                self._last_rssi_time = time.monotonic()
                self.rssi_updated.emit(int(rssi))

    @pyqtSlot('QDBusMessage')
    def _on_interfaces_removed(self, msg: QDBusMessage) -> None:
        """Handle a BlueZ object disappearing (device went out of range)."""
        args = msg.arguments()
        if len(args) < 2:
            return
        path = str(args[0])
        interfaces = args[1]
        if _BLUEZ_DEVICE_IFACE not in interfaces:
            return
        if self._monitoring and path == self._target_path:
            log.info("Target device disappeared: %s", self._target_mac)
            self.device_disappeared.emit()

    # ------------------------------------------------------------------ #
    # hcitool fallback for stale RSSI                                      #
    # ------------------------------------------------------------------ #

    def _on_stale_check(self) -> None:
        """Poll RSSI for classic BT devices if no D-Bus updates have been received."""
        if not self._monitoring or not self._target_mac:
            return

        # Optimization: only poll if we haven't received a D-Bus update recently.
        # This reduces unnecessary subprocess calls for devices that emit regular
        # RSSI updates via PropertiesChanged.
        # Use 2.5x the poll interval as the threshold for 'stale'.
        if time.monotonic() - self._last_rssi_time < (_RSSI_POLL_MS / 1_000 * 2.5):
            return

        rssi, _err, tool = poll_rssi(self._target_mac, self._rssi_method)

        if rssi is not None:
            if not self._using_poll or self._poll_tool != tool:
                log.info("Switching to %s polling for %s", tool, self._target_mac)
                self._using_poll = True
                self._poll_tool = tool
            log.debug("RSSI from poll (%s): %d dBm", tool, rssi)
            self._last_rssi_time = time.monotonic()
            self.rssi_updated.emit(rssi)
            if not self._poll_reachable:
                self._poll_reachable = True
                log.info("Device reachable (poll): %s", self._target_mac)
                self.device_appeared.emit()
        else:
            if self._poll_reachable:
                self._poll_reachable = False
                log.info("Device unreachable (poll): %s", self._target_mac)
                self.device_disappeared.emit()

    # ------------------------------------------------------------------ #
    # Utility: enumerate currently known devices from BlueZ                #
    # ------------------------------------------------------------------ #

    def get_known_devices(self) -> list[DeviceInfo]:
        """Return devices currently known to BlueZ (no scan needed)."""
        msg = QDBusMessage.createMethodCall(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "GetManagedObjects")
        reply = self._bus.call(msg)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            log.warning("GetManagedObjects failed: %s", reply.errorMessage())
            return []

        devices = []
        objects = reply.arguments()[0] if reply.arguments() else {}
        for _path, interfaces in objects.items():
            if _BLUEZ_DEVICE_IFACE not in interfaces:
                continue
            props = interfaces[_BLUEZ_DEVICE_IFACE]
            mac = normalize_mac(props.get("Address", ""))
            if mac:
                devices.append(DeviceInfo(
                    mac=mac,
                    name=str(props.get("Name", "")),
                    rssi=props.get("RSSI"),
                ))
        return devices
