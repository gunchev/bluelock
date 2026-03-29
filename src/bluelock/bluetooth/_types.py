"""Data types for Bluetooth device discovery and monitoring."""
from __future__ import annotations

import dataclasses
import re

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_mac(mac: str) -> str:
    """Return MAC address in upper-case colon-separated format, or '' if invalid."""
    mac = mac.strip().upper().replace("-", ":")
    return mac if _MAC_RE.match(mac) else ""


def mac_to_dbus_path(adapter_path: str, mac: str) -> str:
    """Convert a MAC address to a BlueZ D-Bus object path segment.

    Example: 'AA:BB:CC:DD:EE:FF' → '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF'
    """
    return f"{adapter_path}/dev_{mac.replace(':', '_')}"


@dataclasses.dataclass(frozen=True)
class DeviceInfo:
    """A discovered Bluetooth device."""

    mac: str          # upper-case, colon-separated
    name: str         # friendly name (may be empty)
    rssi: int | None  # RSSI at discovery time, dBm (None if not reported)

    def __str__(self) -> str:
        label = self.name if self.name else self.mac
        rssi_str = f" ({self.rssi} dBm)" if self.rssi is not None else ""
        return f"{label}{rssi_str}"
