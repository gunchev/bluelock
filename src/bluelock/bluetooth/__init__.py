"""Bluetooth monitoring package."""
from bluelock.bluetooth._adapters import AdapterInfo, list_adapters, resolve_addresses
from bluelock.bluetooth._base import AbstractBluetoothMonitor
from bluelock.bluetooth._types import DeviceInfo, mac_to_dbus_path, normalize_mac


def get_monitor() -> AbstractBluetoothMonitor:
    """Return the best available Bluetooth monitor for this system."""
    from bluelock.bluetooth._bluez_dbus import BluezDBusMonitor
    return BluezDBusMonitor()


__all__ = [
    "AbstractBluetoothMonitor",
    "AdapterInfo",
    "DeviceInfo",
    "get_monitor",
    "list_adapters",
    "mac_to_dbus_path",
    "normalize_mac",
    "resolve_addresses",
]
