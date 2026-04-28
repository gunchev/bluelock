"""Abstract base class for Bluetooth monitors."""
from __future__ import annotations

from abc import abstractmethod

from PyQt6.QtCore import QObject, pyqtSignal

from bluelock.bluetooth._types import DeviceInfo


class AbstractBluetoothMonitor(QObject):
    """Interface for Bluetooth proximity monitoring.

    Subclasses implement the actual Bluetooth communication.
    All signals are emitted on the Qt main thread.
    """

    # Aggregated smoothed RSSI across all selected adapters (dBm)
    rssi_updated = pyqtSignal(int)

    # Per-adapter RSSI sample (adapter_address, dBm) — for UI debugging
    adapter_rssi_updated = pyqtSignal(str, int)

    # Emitted when the target device becomes visible on at least one selected adapter
    device_appeared = pyqtSignal()

    # Emitted when the target device is no longer visible on any selected adapter
    device_disappeared = pyqtSignal()

    # Emitted when the bound set of adapters changes (hot-plug, Powered toggle)
    adapters_changed = pyqtSignal()

    # Emitted for each device found during a scan
    scan_result = pyqtSignal(DeviceInfo)

    # Emitted when a scan completes or times out
    scan_finished = pyqtSignal()

    # Emitted on non-fatal errors (adapter gone, D-Bus failure, etc.)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @abstractmethod
    def start_monitoring(self, mac: str, adapter_addresses: list[str] | None = None) -> None:
        """Begin RSSI monitoring for the device with the given MAC address.

        *adapter_addresses* is a list of adapter BD addresses; an empty list
        or None means "use all currently available adapters".
        """

    @abstractmethod
    def stop_monitoring(self) -> None:
        """Stop RSSI monitoring."""

    @abstractmethod
    def start_scan(self, timeout_ms: int = 10_000) -> None:
        """Scan for nearby Bluetooth devices, emitting scan_result for each."""

    @abstractmethod
    def stop_scan(self) -> None:
        """Stop an in-progress scan early."""

    @property
    @abstractmethod
    def is_monitoring(self) -> bool:
        """True if currently monitoring a device."""

    @property
    @abstractmethod
    def is_scanning(self) -> bool:
        """True if currently scanning."""
