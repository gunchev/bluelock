"""Configuration dialog."""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bluelock.bluetooth._types import DeviceInfo
from bluelock.config import Config, DeviceConfig
from bluelock.signal_processor import estimate_distance_m

_AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "bluelock.desktop"
_AUTOSTART_CONTENT = """\
[Desktop Entry]
Type=Application
Name=BlueLock
Exec=bluelock
Icon=bluelock
Comment=Lock and unlock your session based on Bluetooth proximity
X-GNOME-Autostart-enabled=true
"""
_RSSI_MIN = -100
_RSSI_MAX = 0

log = logging.getLogger(__name__)


def _autostart_enabled() -> bool:
    return _AUTOSTART_FILE.exists()


def _set_autostart(enabled: bool) -> None:
    if enabled:
        _AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        _AUTOSTART_FILE.write_text(_AUTOSTART_CONTENT)
    elif _AUTOSTART_FILE.exists():
        _AUTOSTART_FILE.unlink()


def _rssi_spinbox(default: int) -> QSpinBox:
    spin = QSpinBox()
    spin.setRange(_RSSI_MIN, _RSSI_MAX)
    spin.setSuffix(" dBm")
    spin.setValue(default)
    return spin


def _rssi_slider(default: int) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(_RSSI_MIN, _RSSI_MAX)
    slider.setValue(default)
    return slider


class _DeviceTab(QWidget):
    """Per-device settings tab with signal display, thresholds, commands and a forget button."""

    forget_requested = pyqtSignal(str)  # emits MAC address

    def __init__(self, dev: DeviceConfig, buffer_size: int = 16, scan_interval: float = 1.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mac = dev.mac
        self._name = dev.name

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.addWidget(self._build_signal_group())
        layout.addWidget(self._build_thresholds_group())
        layout.addWidget(self._build_commands_group())
        layout.addWidget(self._build_advanced_group())
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll, stretch=1)

        forget_btn = QPushButton(f"Forget {dev.mac}")
        forget_btn.clicked.connect(lambda: self.forget_requested.emit(self._mac))
        outer.addWidget(forget_btn)

        self._populate(dev, buffer_size, scan_interval)

    @property
    def buffer_size(self) -> int:
        return self._buffer_spin.value()

    @property
    def scan_interval(self) -> float:
        return self._interval_spin.value()

    @property
    def autostart_enabled(self) -> bool:
        return self._autostart_check.isChecked()

    def to_device_config(self) -> DeviceConfig:
        return DeviceConfig(
            mac=self._mac,
            name=self._name,
            lock_rssi_threshold=self._lock_rssi_spin.value(),
            lock_duration=self._lock_dur_spin.value(),
            unlock_rssi_threshold=self._unlock_rssi_spin.value(),
            unlock_duration=self._unlock_dur_spin.value(),
            lock_command=self._lock_cmd_edit.text().strip(),
            unlock_command=self._unlock_cmd_edit.text().strip(),
        )

    def update_rssi(self, rssi: int) -> None:
        self._rssi_bar.setValue(max(_RSSI_MIN, min(_RSSI_MAX, rssi)))
        self._rssi_label.setText(f"RSSI: {rssi} dBm")
        dist = estimate_distance_m(rssi)
        if dist < 999:
            self._dist_label.setText(f"Distance: ≈{dist:.1f} m")
        else:
            self._dist_label.setText("Distance: —")

    def _build_signal_group(self) -> QGroupBox:
        box = QGroupBox("Signal Strength")
        layout = QVBoxLayout(box)
        self._rssi_bar = QProgressBar()
        self._rssi_bar.setRange(_RSSI_MIN, _RSSI_MAX)
        self._rssi_bar.setValue(_RSSI_MIN)
        self._rssi_bar.setFormat("%v dBm")
        layout.addWidget(self._rssi_bar)
        info_row = QHBoxLayout()
        self._rssi_label = QLabel("RSSI: —")
        self._dist_label = QLabel("Distance: —")
        info_row.addWidget(self._rssi_label)
        info_row.addStretch()
        info_row.addWidget(self._dist_label)
        layout.addLayout(info_row)
        return box

    def _build_thresholds_group(self) -> QGroupBox:
        box = QGroupBox("Thresholds")
        form = QFormLayout(box)

        self._lock_rssi_spin = _rssi_spinbox(-15)
        self._lock_rssi_slider = _rssi_slider(-15)
        self._lock_rssi_spin.valueChanged.connect(self._lock_rssi_slider.setValue)
        self._lock_rssi_slider.valueChanged.connect(self._lock_rssi_spin.setValue)
        lock_rssi_row = QHBoxLayout()
        lock_rssi_row.addWidget(self._lock_rssi_slider)
        lock_rssi_row.addWidget(self._lock_rssi_spin)
        form.addRow("Lock RSSI threshold:", lock_rssi_row)

        self._lock_dur_spin = QSpinBox()
        self._lock_dur_spin.setRange(1, 120)
        self._lock_dur_spin.setSuffix(" s")
        form.addRow("Lock duration:", self._lock_dur_spin)

        self._unlock_rssi_spin = _rssi_spinbox(-10)
        self._unlock_rssi_slider = _rssi_slider(-10)
        self._unlock_rssi_spin.valueChanged.connect(self._unlock_rssi_slider.setValue)
        self._unlock_rssi_slider.valueChanged.connect(self._unlock_rssi_spin.setValue)
        unlock_rssi_row = QHBoxLayout()
        unlock_rssi_row.addWidget(self._unlock_rssi_slider)
        unlock_rssi_row.addWidget(self._unlock_rssi_spin)
        form.addRow("Unlock RSSI threshold:", unlock_rssi_row)

        self._unlock_dur_spin = QSpinBox()
        self._unlock_dur_spin.setRange(1, 120)
        self._unlock_dur_spin.setSuffix(" s")
        form.addRow("Unlock duration:", self._unlock_dur_spin)

        return box

    def _build_commands_group(self) -> QGroupBox:
        box = QGroupBox("Lock / Unlock Commands")
        form = QFormLayout(box)
        self._lock_cmd_edit = QLineEdit()
        self._lock_cmd_edit.setPlaceholderText("Leave empty to use D-Bus ScreenSaver")
        form.addRow("Lock command:", self._lock_cmd_edit)
        self._unlock_cmd_edit = QLineEdit()
        self._unlock_cmd_edit.setPlaceholderText("Leave empty to use D-Bus ScreenSaver")
        form.addRow("Unlock command:", self._unlock_cmd_edit)
        return box

    def _build_advanced_group(self) -> QGroupBox:
        box = QGroupBox("Advanced")
        form = QFormLayout(box)
        self._buffer_spin = QSpinBox()
        self._buffer_spin.setRange(1, 255)
        self._buffer_spin.setToolTip("Number of RSSI readings to average")
        form.addRow("Buffer size:", self._buffer_spin)
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.5, 10.0)
        self._interval_spin.setSingleStep(0.5)
        self._interval_spin.setSuffix(" s")
        self._interval_spin.setToolTip("How often to evaluate the lock/unlock state")
        form.addRow("Scan interval:", self._interval_spin)
        self._autostart_check = QCheckBox("Start BlueLock automatically on login")
        form.addRow("Auto-start:", self._autostart_check)
        return box

    def _populate(self, dev: DeviceConfig, buffer_size: int, scan_interval: float) -> None:
        self._lock_rssi_spin.setValue(dev.lock_rssi_threshold)
        self._lock_rssi_slider.setValue(dev.lock_rssi_threshold)
        self._lock_dur_spin.setValue(dev.lock_duration)
        self._unlock_rssi_spin.setValue(dev.unlock_rssi_threshold)
        self._unlock_rssi_slider.setValue(dev.unlock_rssi_threshold)
        self._unlock_dur_spin.setValue(dev.unlock_duration)
        self._lock_cmd_edit.setText(dev.lock_command)
        self._unlock_cmd_edit.setText(dev.unlock_command)
        self._buffer_spin.setValue(buffer_size)
        self._interval_spin.setValue(scan_interval)
        self._autostart_check.setChecked(_autostart_enabled())


class ConfigDialog(QDialog):
    """Configuration dialog."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BlueLock — Preferences")
        self.setMinimumSize(720, 690)

        self._config = config
        self._monitor = None
        self._scan_results: dict[str, DeviceInfo] = {}
        self._device_tab: _DeviceTab | None = None

        self._build_ui()

        if config.device:
            self._set_device_tab(config.device, config.buffer_size, config.scan_interval)

    # ------------------------------------------------------------------ #
    # Public                                                               #
    # ------------------------------------------------------------------ #

    def connect_monitor(self, monitor) -> None:
        """Connect to a Bluetooth monitor's signals."""
        self._monitor = monitor
        monitor.rssi_updated.connect(self._on_rssi_update)
        monitor.scan_result.connect(self._on_scan_result)
        monitor.scan_finished.connect(self._on_scan_finished)

    def current_config(self) -> Config:
        """Return a Config built from the current dialog state."""
        return Config(
            device=self._device_tab.to_device_config() if self._device_tab else None,
            buffer_size=self._device_tab.buffer_size if self._device_tab else 16,
            scan_interval=self._device_tab.scan_interval if self._device_tab else 1.0,
        )

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_scanner_tab(), "Devices")
        layout.addWidget(self._tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_scanner_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # MAC input + scan/use controls
        top = QWidget()
        top_form = QFormLayout(top)
        top_form.setContentsMargins(0, 0, 0, 0)
        self._mac_edit = QLineEdit()
        self._mac_edit.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        self._use_btn = QPushButton("Use")
        self._use_btn.clicked.connect(self._on_device_selected)
        mac_row = QHBoxLayout()
        mac_row.addWidget(self._mac_edit)
        mac_row.addWidget(self._scan_btn)
        mac_row.addWidget(self._use_btn)
        top_form.addRow("MAC address:", mac_row)
        layout.addWidget(top)

        # Device table — expands to fill
        self._device_table = QTableWidget(0, 2)
        self._device_table.setHorizontalHeaderLabels(["MAC", "Name"])
        self._device_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._device_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._device_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._device_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._device_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._device_table.itemDoubleClicked.connect(self._on_device_selected)
        layout.addWidget(self._device_table, stretch=1)

        return tab

    def _set_device_tab(self, dev: DeviceConfig, buffer_size: int = 16, scan_interval: float = 1.0) -> int:
        """Create or update the settings tab for *dev*, lock the Device tab, and return the index."""
        if self._device_tab:
            self._tabs.removeTab(1)

        self._device_tab = _DeviceTab(dev, buffer_size, scan_interval)
        self._device_tab.forget_requested.connect(self._on_forget)
        idx = self._tabs.addTab(self._device_tab, "Settings")
        self._tabs.setTabEnabled(0, False)
        self._tabs.setCurrentIndex(idx)
        return idx

    # ------------------------------------------------------------------ #
    # Slot handlers                                                        #
    # ------------------------------------------------------------------ #

    def _on_rssi_update(self, rssi: int) -> None:
        if self._device_tab:
            self._device_tab.update_rssi(rssi)

    def _on_scan_clicked(self) -> None:
        self._scan_btn.setEnabled(False)
        self._scan_btn.setText("Scanning…")
        self._device_table.setRowCount(0)
        self._scan_results.clear()
        QTimer.singleShot(12_000, self._on_scan_done)
        if self._monitor is not None:
            self._monitor.start_scan()

    def _on_scan_done(self) -> None:
        self._scan_btn.setEnabled(True)
        self._scan_btn.setText("Scan")

    def _on_scan_result(self, device: DeviceInfo) -> None:
        if device.mac in self._scan_results:
            return
        self._scan_results[device.mac] = device
        row = self._device_table.rowCount()
        self._device_table.insertRow(row)
        self._device_table.setItem(row, 0, QTableWidgetItem(device.mac))
        self._device_table.setItem(row, 1, QTableWidgetItem(device.name))

    def _on_scan_finished(self) -> None:
        self._on_scan_done()

    def _on_accept(self) -> None:
        try:
            _set_autostart(self._device_tab.autostart_enabled if self._device_tab else False)
        except OSError as e:
            log.warning("Could not update autostart entry: %s", e)
        self.accept()

    def _on_device_selected(self) -> None:
        """Use the selected device: create its settings tab and lock the Device tab."""
        row = self._device_table.currentRow()
        mac = self._mac_edit.text().strip()
        name = ""
        if row >= 0:
            mac_item = self._device_table.item(row, 0)
            name_item = self._device_table.item(row, 1)
            if mac_item:
                mac = mac_item.text()
            if name_item:
                name = name_item.text()

        if not mac:
            return

        self._set_device_tab(DeviceConfig(mac=mac, name=name))

    def _on_forget(self, mac: str) -> None:
        """Remove the device tab and unlock the Device tab."""
        if self._device_tab is None:
            return
        self._device_tab = None
        self._tabs.removeTab(1)
        self._tabs.setTabEnabled(0, True)
        self._tabs.setCurrentIndex(0)
