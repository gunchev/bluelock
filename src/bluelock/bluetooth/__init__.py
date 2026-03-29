"""Bluetooth monitoring package."""
from bluelock.bluetooth._base import AbstractBluetoothMonitor
from bluelock.bluetooth._types import DeviceInfo, mac_to_dbus_path, normalize_mac


def get_monitor() -> AbstractBluetoothMonitor:
    """Return the best available Bluetooth monitor for this system."""
    from bluelock.bluetooth._bluez_dbus import BluezDBusMonitor
    return BluezDBusMonitor()


__all__ = [
    "AbstractBluetoothMonitor",
    "DeviceInfo",
    "get_monitor",
    "mac_to_dbus_path",
    "normalize_mac",
]
