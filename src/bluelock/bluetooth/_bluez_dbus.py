"""BlueZ D-Bus Bluetooth monitor using PyQt6.QtDBus.

Multi-adapter aware: subscribes to RSSI updates from every selected adapter,
aggregates by ``max(latest fresh sample)``, and tracks adapter hot-plug.
"""
from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable

from PyQt6.QtCore import QObject, QTimer, pyqtSlot
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

from bluelock.bluetooth._adapters import AdapterInfo, list_adapters, resolve_addresses
from bluelock.bluetooth._base import AbstractBluetoothMonitor
from bluelock.bluetooth._types import DeviceInfo, mac_to_dbus_path, normalize_mac
from bluelock.bluetooth._utils import poll_rssi

log = logging.getLogger(__name__)

_BLUEZ_SVC = "org.bluez"
_BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
_BLUEZ_DEVICE_IFACE = "org.bluez.Device1"
_DBUS_OBJMGR_IFACE = "org.freedesktop.DBus.ObjectManager"
_DBUS_PROPS_IFACE = "org.freedesktop.DBus.Properties"

_RSSI_POLL_MS = 2_000
# A per-adapter sample is considered fresh if newer than this many seconds.
# Beyond it, that adapter no longer contributes to the aggregate or to presence.
_STALE_WINDOW_S = 5.0
# Late-bind retry delay when StartDiscovery races with adapter initialisation.
_DISCOVERY_RETRY_MS = 250


@dataclasses.dataclass
class _AdapterState:
    """Per-adapter runtime state for the monitored device."""

    info: AdapterInfo
    device_path: str = ""
    latest_rssi: int | None = None
    latest_ts: float = 0.0
    connected: bool = False
    discovery_started: bool = False
    using_poll: bool = False
    poll_tool: str = ""


class BluezDBusMonitor(AbstractBluetoothMonitor):
    """Monitors Bluetooth device proximity across one or more BlueZ adapters.

    Per adapter: subscribe to ``PropertiesChanged`` on the device path, fall back
    to subprocess polling on stale samples. The class also listens to BlueZ
    ``InterfacesAdded``/``InterfacesRemoved`` for adapter hot-plug and to
    ``PropertiesChanged`` on adapters for ``Powered`` toggles.
    """

    def __init__(self, parent: QObject | None = None, *, clock: Callable[[], float] | None = None) -> None:
        super().__init__(parent)
        self._bus = QDBusConnection.systemBus()
        self._clock = clock or time.monotonic

        self._target_mac: str = ""
        self._monitoring: bool = False
        self._scanning: bool = False
        self._rssi_method: str = "auto"

        # Configured selection (BD addresses); empty ⇒ use all available adapters.
        self._selected_addresses: list[str] = []
        # Bound adapter state, keyed by adapter BD address.
        self._adapter_states: dict[str, _AdapterState] = {}
        # All adapter paths known to BlueZ (incl. unselected/unpowered) → BD address.
        # Populated at monitoring start and via InterfacesAdded; used by
        # _on_adapter_props_changed so it can pass the address to _handle_powered.
        self._adapter_path_to_address: dict[str, str] = {}
        # Aggregate presence for edge-triggered appeared/disappeared.
        self._aggregate_present: bool = False
        # Adapters used while scanning (may overlap with monitored ones).
        self._scan_adapters: list[AdapterInfo] = []
        # ObjectManager subscription is active while monitoring or scanning.
        self._objmgr_connected: bool = False

        self._stale_timer = QTimer(self)
        self._stale_timer.setInterval(_RSSI_POLL_MS)
        self._stale_timer.timeout.connect(self._on_stale_check)

        self._scan_timer = QTimer(self)
        self._scan_timer.setSingleShot(True)
        self._scan_timer.timeout.connect(self.stop_scan)

        if not self._bus.isConnected():
            log.error("Cannot connect to D-Bus system bus")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def start_monitoring(self, mac: str, adapter_addresses: list[str] | None = None) -> None:
        mac = normalize_mac(mac)
        if not mac:
            self.error_occurred.emit(f"Invalid MAC address: {mac!r}")
            return

        if self._monitoring:
            self.stop_monitoring()

        self._target_mac = mac
        self._selected_addresses = [normalize_mac(a) for a in (adapter_addresses or []) if normalize_mac(a)]
        self._monitoring = True
        self._aggregate_present = False
        log.info("Starting monitoring for %s on adapters=%s",
                 mac, self._selected_addresses or "all")

        self._connect_object_manager_signals()
        self._start_adapter_watching()

        adapters = self._resolve_initial_adapters()
        if not adapters:
            log.warning("No Bluetooth adapters available; monitoring will yield no data")
        for ainfo in adapters:
            self._bind_adapter(ainfo)

        self._stale_timer.start()

    def stop_monitoring(self) -> None:
        if not self._monitoring:
            return
        log.info("Stopping monitoring for %s", self._target_mac)
        self._stale_timer.stop()
        for addr in list(self._adapter_states.keys()):
            self._unbind_adapter(addr)
        self._stop_adapter_watching()
        if not self._scanning:
            self._disconnect_object_manager_signals()
        self._monitoring = False
        self._target_mac = ""
        self._selected_addresses = []
        self._aggregate_present = False

    def start_scan(self, timeout_ms: int = 10_000) -> None:
        if self._scanning:
            return
        log.info("Starting device scan (timeout=%dms)", timeout_ms)
        self._scanning = True
        self._connect_object_manager_signals()

        # Scan on every currently available adapter.
        self._scan_adapters = [a for a in list_adapters() if a.address and a.powered]
        for ainfo in self._scan_adapters:
            self._start_discovery(ainfo.path)

        self._scan_timer.start(timeout_ms)
        for device in self.get_known_devices():
            self.scan_result.emit(device)

    def stop_scan(self) -> None:
        if not self._scanning:
            return
        log.info("Stopping device scan")
        self._scan_timer.stop()
        # StopDiscovery on adapters used solely for scanning (not also being monitored).
        monitored_paths = {s.info.path for s in self._adapter_states.values()}
        for ainfo in self._scan_adapters:
            if ainfo.path not in monitored_paths:
                self._stop_discovery(ainfo.path)
        self._scan_adapters = []
        if not self._monitoring:
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

    @property
    def bound_adapters(self) -> list[AdapterInfo]:
        """Adapters currently bound for monitoring (read-only snapshot)."""
        return [s.info for s in self._adapter_states.values()]

    # ------------------------------------------------------------------ #
    # Adapter binding                                                      #
    # ------------------------------------------------------------------ #

    def _resolve_initial_adapters(self) -> list[AdapterInfo]:
        all_adapters = list_adapters(self._bus)
        resolved = resolve_addresses(self._selected_addresses, adapters=all_adapters)
        # Skip adapters that are unpowered or have no usable address.
        return [a for a in resolved if a.address and a.powered]

    def _is_selected(self, address: str) -> bool:
        if not address:
            return False
        if not self._selected_addresses:
            return True
        return address in self._selected_addresses

    def _bind_adapter(self, ainfo: AdapterInfo) -> None:
        if not ainfo.address:
            log.warning("Cannot bind adapter %s: missing BD address", ainfo.path)
            return
        if ainfo.address in self._adapter_states:
            return
        device_path = mac_to_dbus_path(ainfo.path, self._target_mac) if self._target_mac else ""
        state = _AdapterState(info=ainfo, device_path=device_path)
        self._adapter_states[ainfo.address] = state
        log.info("Binding adapter %s (%s)", ainfo.address, ainfo.path)

        if device_path:
            self._connect_device_signals(device_path)
        self._connect_adapter_props(ainfo.path)
        self._start_discovery(ainfo.path, on_state=state)
        self.adapters_changed.emit()

    def _unbind_adapter(self, address: str, *, adapter_gone: bool = False) -> None:
        state = self._adapter_states.pop(address, None)
        if state is None:
            return
        log.info("Unbinding adapter %s%s", address, " (gone)" if adapter_gone else "")
        if not adapter_gone:
            if state.discovery_started:
                self._stop_discovery(state.info.path)
            if state.device_path:
                self._disconnect_device_signals(state.device_path)
        self._recompute_aggregate()
        self.adapters_changed.emit()

    # ------------------------------------------------------------------ #
    # Aggregation                                                          #
    # ------------------------------------------------------------------ #

    def _state_present(self, state: _AdapterState, now: float) -> bool:
        if state.connected:
            return True
        if state.latest_rssi is None:
            return False
        return (now - state.latest_ts) < _STALE_WINDOW_S

    def _recompute_aggregate(self) -> None:
        now = self._clock()
        fresh = [s for s in self._adapter_states.values()
                 if s.latest_rssi is not None and (now - s.latest_ts) < _STALE_WINDOW_S]
        if fresh:
            best = max(s.latest_rssi for s in fresh)  # type: ignore[type-var]
            self.rssi_updated.emit(int(best))

        any_present = any(self._state_present(s, now) for s in self._adapter_states.values())
        if any_present and not self._aggregate_present:
            self._aggregate_present = True
            self.device_appeared.emit()
        elif not any_present and self._aggregate_present:
            self._aggregate_present = False
            self.device_disappeared.emit()

    # ------------------------------------------------------------------ #
    # Internal handlers — testable seams                                   #
    # ------------------------------------------------------------------ #

    def _handle_rssi(self, address: str, rssi: int, *, source: str = "dbus") -> None:
        state = self._adapter_states.get(address)
        if state is None:
            return
        if source == "dbus" and state.using_poll:
            log.info("Switching to D-Bus RSSI updates for %s on %s", self._target_mac, address)
            state.using_poll = False
            state.poll_tool = ""
        elif source != "dbus":
            tool = source
            if not state.using_poll or state.poll_tool != tool:
                log.info("Switching to %s polling for %s on %s", tool, self._target_mac, address)
                state.using_poll = True
                state.poll_tool = tool
        state.latest_rssi = int(rssi)
        state.latest_ts = self._clock()
        self.adapter_rssi_updated.emit(address, int(rssi))
        self._recompute_aggregate()

    def _handle_connected(self, address: str, connected: bool) -> None:
        state = self._adapter_states.get(address)
        if state is None:
            return
        state.connected = bool(connected)
        log.info("Device %s: Connected=%s on %s", self._target_mac, connected, address)
        self._recompute_aggregate()

    def _handle_adapter_added(self, ainfo: AdapterInfo) -> None:
        if not self._monitoring:
            return
        if not self._is_selected(ainfo.address):
            return
        if not ainfo.powered:
            log.info("Adapter %s appeared but is unpowered; deferring bind", ainfo.address)
            return
        self._bind_adapter(ainfo)

    def _handle_adapter_removed(self, path: str) -> None:
        # Find the state by path (we don't have the address from the removal signal alone).
        for addr, state in list(self._adapter_states.items()):
            if state.info.path == path:
                self._unbind_adapter(addr, adapter_gone=True)
                return

    def _handle_powered(self, path: str, powered: bool, *, address: str = "", alias: str = "") -> None:
        # Find state by path; if powered=True and no state, this may be a newly powered adapter
        # we previously skipped during bind.
        for addr, state in list(self._adapter_states.items()):
            if state.info.path == path:
                if not powered:
                    self._unbind_adapter(addr)
                elif not state.info.powered:
                    state.info = dataclasses.replace(state.info, powered=True)
                return
        if powered and self._monitoring and address and self._is_selected(address):
            ainfo = AdapterInfo(address=address, path=path, alias=alias, powered=True)
            self._bind_adapter(ainfo)

    # ------------------------------------------------------------------ #
    # D-Bus signal connections                                             #
    # ------------------------------------------------------------------ #

    def _connect_object_manager_signals(self) -> None:
        if self._objmgr_connected:
            return
        self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded", self._on_interfaces_added)
        self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesRemoved", self._on_interfaces_removed)
        self._objmgr_connected = True

    def _disconnect_object_manager_signals(self) -> None:
        if not self._objmgr_connected:
            return
        self._bus.disconnect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded", self._on_interfaces_added)
        self._bus.disconnect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesRemoved", self._on_interfaces_removed)
        self._objmgr_connected = False

    def _connect_device_signals(self, path: str) -> None:
        ok = self._bus.connect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_properties_changed)
        if not ok:
            log.warning("Failed to connect PropertiesChanged for %s: %s", path, self._bus.lastError().message())

    def _disconnect_device_signals(self, path: str) -> None:
        self._bus.disconnect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_properties_changed)

    def _connect_adapter_props(self, path: str) -> None:
        self._bus.connect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_adapter_props_changed)

    def _disconnect_adapter_props(self, path: str) -> None:
        self._bus.disconnect(_BLUEZ_SVC, path, _DBUS_PROPS_IFACE, "PropertiesChanged", self._on_adapter_props_changed)

    def _start_adapter_watching(self) -> None:
        """Subscribe to PropertiesChanged for all currently-known adapters and build the path→address cache.

        Called once at monitoring start so that power-on signals are received even for
        adapters that were unpowered or unselected at startup.
        """
        for ainfo in list_adapters(self._bus):
            if not ainfo.path:
                continue
            if ainfo.address:
                self._adapter_path_to_address[ainfo.path] = ainfo.address
            self._connect_adapter_props(ainfo.path)

    def _stop_adapter_watching(self) -> None:
        for path in list(self._adapter_path_to_address):
            self._disconnect_adapter_props(path)
        self._adapter_path_to_address.clear()

    # ------------------------------------------------------------------ #
    # BlueZ adapter control                                                #
    # ------------------------------------------------------------------ #

    def _start_discovery(self, adapter_path: str, *, on_state: _AdapterState | None = None) -> None:
        adapter = QDBusInterface(_BLUEZ_SVC, adapter_path, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StartDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            err = reply.errorMessage()
            if "InProgress" in err:
                log.debug("StartDiscovery on %s: already in progress", adapter_path)
                if on_state is not None:
                    on_state.discovery_started = True
                return
            if "NotReady" in err and on_state is not None:
                log.debug("StartDiscovery on %s: NotReady, retrying in %dms", adapter_path, _DISCOVERY_RETRY_MS)
                QTimer.singleShot(_DISCOVERY_RETRY_MS,
                                  lambda: self._retry_start_discovery(adapter_path, on_state))
                return
            log.warning("StartDiscovery on %s failed: %s", adapter_path, err)
            self.error_occurred.emit(f"Bluetooth discovery error on {adapter_path}: {err}")
            return
        if on_state is not None:
            on_state.discovery_started = True

    def _retry_start_discovery(self, adapter_path: str, state: _AdapterState) -> None:
        # The adapter may have been unbound in the meantime.
        current = self._adapter_states.get(state.info.address)
        if current is not state:
            return
        adapter = QDBusInterface(_BLUEZ_SVC, adapter_path, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StartDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            err = reply.errorMessage()
            if "InProgress" in err:
                state.discovery_started = True
                return
            log.warning("StartDiscovery retry on %s failed: %s", adapter_path, err)
            return
        state.discovery_started = True

    def _stop_discovery(self, adapter_path: str) -> None:
        adapter = QDBusInterface(_BLUEZ_SVC, adapter_path, _BLUEZ_ADAPTER_IFACE, self._bus)
        reply = adapter.call("StopDiscovery")
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            log.debug("StopDiscovery on %s: %s", adapter_path, reply.errorMessage())

    # ------------------------------------------------------------------ #
    # D-Bus signal handlers                                                #
    # ------------------------------------------------------------------ #

    def _adapter_address_for_device_path(self, device_path: str) -> str:
        """Return the adapter BD address whose path is the parent of *device_path*."""
        for addr, state in self._adapter_states.items():
            if state.device_path and device_path == state.device_path:
                return addr
        return ""

    @pyqtSlot('QDBusMessage')
    def _on_properties_changed(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if not args:
            return
        iface = str(args[0])
        if iface != _BLUEZ_DEVICE_IFACE:
            return
        addr = self._adapter_address_for_device_path(msg.path())
        if not addr:
            return
        changed = args[1] if len(args) > 1 else {}
        if "RSSI" in changed:
            self._handle_rssi(addr, int(changed["RSSI"]), source="dbus")
        if "Connected" in changed:
            self._handle_connected(addr, bool(changed["Connected"]))

    @pyqtSlot('QDBusMessage')
    def _on_adapter_props_changed(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if not args:
            return
        iface = str(args[0])
        if iface != _BLUEZ_ADAPTER_IFACE:
            return
        changed = args[1] if len(args) > 1 else {}
        if "Powered" not in changed:
            return
        address = self._adapter_path_to_address.get(msg.path(), "")
        self._handle_powered(msg.path(), bool(changed["Powered"]), address=address)

    @pyqtSlot('QDBusMessage')
    def _on_interfaces_added(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if len(args) < 2:
            return
        path = str(args[0])
        interfaces = args[1]

        if _BLUEZ_ADAPTER_IFACE in interfaces:
            props = interfaces[_BLUEZ_ADAPTER_IFACE]
            address = normalize_mac(str(props.get("Address", "")))
            ainfo = AdapterInfo(
                address=address,
                path=path,
                alias=str(props.get("Alias", "")),
                powered=bool(props.get("Powered", False)),
            )
            if address:
                self._adapter_path_to_address[path] = address
            if self._monitoring:
                self._connect_adapter_props(path)
            self._handle_adapter_added(ainfo)

        if _BLUEZ_DEVICE_IFACE in interfaces:
            props = interfaces[_BLUEZ_DEVICE_IFACE]
            mac = normalize_mac(str(props.get("Address", "")))
            name = str(props.get("Name", ""))
            rssi = props.get("RSSI")
            if not mac:
                return
            if self._scanning:
                self.scan_result.emit(DeviceInfo(mac=mac, name=name, rssi=rssi))
            if self._monitoring and mac == self._target_mac:
                # Find which adapter this device belongs to by path prefix.
                for addr, state in self._adapter_states.items():
                    if path.startswith(state.info.path + "/"):
                        state.device_path = path
                        self._connect_device_signals(path)
                        if rssi is not None:
                            self._handle_rssi(addr, int(rssi), source="dbus")
                        else:
                            self._handle_connected(addr, True)
                        break

    @pyqtSlot('QDBusMessage')
    def _on_interfaces_removed(self, msg: QDBusMessage) -> None:
        args = msg.arguments()
        if len(args) < 2:
            return
        path = str(args[0])
        interfaces = args[1]
        if _BLUEZ_ADAPTER_IFACE in interfaces:
            self._adapter_path_to_address.pop(path, None)
            self._disconnect_adapter_props(path)
            self._handle_adapter_removed(path)
            return
        if _BLUEZ_DEVICE_IFACE in interfaces and self._monitoring:
            for addr, state in self._adapter_states.items():
                if state.device_path and state.device_path == path:
                    state.connected = False
                    state.latest_rssi = None
                    state.latest_ts = 0.0
                    self._recompute_aggregate()
                    log.info("Target device disappeared on adapter %s", addr)
                    return

    # ------------------------------------------------------------------ #
    # Polling fallback (per adapter)                                       #
    # ------------------------------------------------------------------ #

    def _on_stale_check(self) -> None:
        if not self._monitoring or not self._target_mac:
            return
        if self._rssi_method != "dbus":
            now = self._clock()
            for addr, state in list(self._adapter_states.items()):
                if state.latest_rssi is not None and (now - state.latest_ts) < _STALE_WINDOW_S:
                    continue
                rssi, _err, tool = poll_rssi(self._target_mac, self._rssi_method, adapter=state.info.hci_name)
                if rssi is not None:
                    self._handle_rssi(addr, rssi, source=tool)
        self._recompute_aggregate()

    # ------------------------------------------------------------------ #
    # Utility: enumerate currently known devices from BlueZ                #
    # ------------------------------------------------------------------ #

    def get_known_devices(self) -> list[DeviceInfo]:
        msg = QDBusMessage.createMethodCall(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "GetManagedObjects")
        reply = self._bus.call(msg)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            log.warning("GetManagedObjects failed: %s", reply.errorMessage())
            return []

        devices = []
        objects = reply.arguments()[0] if reply.arguments() else {}
        seen: set[str] = set()
        for _path, interfaces in objects.items():
            if _BLUEZ_DEVICE_IFACE not in interfaces:
                continue
            props = interfaces[_BLUEZ_DEVICE_IFACE]
            mac = normalize_mac(props.get("Address", ""))
            if mac and mac not in seen:
                seen.add(mac)
                devices.append(DeviceInfo(
                    mac=mac,
                    name=str(props.get("Name", "")),
                    rssi=props.get("RSSI"),
                ))
        return devices
