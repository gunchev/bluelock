"""Configuration dialog."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
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
from bluelock.config import Config
from bluelock.signal_processor import estimate_distance_m

log = logging.getLogger(__name__)

_RSSI_MIN = -100
_RSSI_MAX = 0


class ConfigDialog(QDialog):
    """Configuration dialog."""

    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BlueLock — Preferences")
        self.setMinimumSize(720, 600)

        self._config = config
        self._monitor = None
        self._scan_results: dict[str, DeviceInfo] = {}

        self._build_ui()
        self._populate(config)
        if config.device_mac:
            self._tabs.setCurrentIndex(1)

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
        return Config(
            device_mac=mac,
            device_name=name,
            lock_rssi_threshold=self._lock_rssi_spin.value(),
            lock_duration=self._lock_dur_spin.value(),
            unlock_rssi_threshold=self._unlock_rssi_spin.value(),
            unlock_duration=self._unlock_dur_spin.value(),
            lock_command=self._lock_cmd_edit.text().strip(),
            unlock_command=self._unlock_cmd_edit.text().strip(),
            buffer_size=self._buffer_spin.value(),
            scan_interval=self._interval_spin.value(),
        )

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_device_tab(), "Device")
        self._tabs.addTab(self._build_settings_tab(), "Settings")
        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_device_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # MAC + Scan controls
        top = QWidget()
        top_form = QFormLayout(top)
        top_form.setContentsMargins(0, 0, 0, 0)
        self._mac_edit = QLineEdit()
        self._mac_edit.setPlaceholderText("AA:BB:CC:DD:EE:FF")
        self._scan_btn = QPushButton("Scan")
        self._scan_btn.clicked.connect(self._on_scan_clicked)
        use_btn = QPushButton("Use")
        use_btn.clicked.connect(self._on_device_selected)
        mac_row = QHBoxLayout()
        mac_row.addWidget(self._mac_edit)
        mac_row.addWidget(self._scan_btn)
        mac_row.addWidget(use_btn)
        top_form.addRow("MAC address:", mac_row)
        layout.addWidget(top)

        # Device table — expands to fill the tab
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

    def _build_settings_tab(self) -> QWidget:
        # Wrap in a scroll area so it stays usable if the window is small
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
        return scroll

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

        self._lock_rssi_spin = self._rssi_spinbox(-15)
        self._lock_rssi_slider = self._rssi_slider(-15)
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

        self._unlock_rssi_spin = self._rssi_spinbox(-10)
        self._unlock_rssi_slider = self._rssi_slider(-10)
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

        return box

    # ------------------------------------------------------------------ #
    # Populate / sync                                                      #
    # ------------------------------------------------------------------ #

    def _populate(self, c: Config) -> None:
        self._mac_edit.setText(c.device_mac)
        self._lock_rssi_spin.setValue(c.lock_rssi_threshold)
        self._lock_rssi_slider.setValue(c.lock_rssi_threshold)
        self._lock_dur_spin.setValue(c.lock_duration)
        self._unlock_rssi_spin.setValue(c.unlock_rssi_threshold)
        self._unlock_rssi_slider.setValue(c.unlock_rssi_threshold)
        self._unlock_dur_spin.setValue(c.unlock_duration)
        self._lock_cmd_edit.setText(c.lock_command)
        self._unlock_cmd_edit.setText(c.unlock_command)
        self._buffer_spin.setValue(c.buffer_size)
        self._interval_spin.setValue(c.scan_interval)

    # ------------------------------------------------------------------ #
    # Slot handlers                                                        #
    # ------------------------------------------------------------------ #

    def _on_rssi_update(self, rssi: int) -> None:
        self._rssi_bar.setValue(max(_RSSI_MIN, min(_RSSI_MAX, rssi)))
        self._rssi_label.setText(f"RSSI: {rssi} dBm")
        dist = estimate_distance_m(rssi)
        if dist < 999:
            self._dist_label.setText(f"Distance: ≈{dist:.1f} m")
        else:
            self._dist_label.setText("Distance: —")

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

    def _on_device_selected(self) -> None:
        row = self._device_table.currentRow()
        if row < 0:
            return
        item = self._device_table.item(row, 0)
        if item:
            self._mac_edit.setText(item.text())
            self._tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rssi_spinbox(default: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(_RSSI_MIN, _RSSI_MAX)
        spin.setSuffix(" dBm")
        spin.setValue(default)
        return spin

    @staticmethod
    def _rssi_slider(default: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(_RSSI_MIN, _RSSI_MAX)
        slider.setValue(default)
        return slider
