"""RSSI history plot dialog."""
from __future__ import annotations

import logging
import time

from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QToolTip, QVBoxLayout, QWidget

from bluelock.bluetooth._base import AbstractBluetoothMonitor
from bluelock.rssi_history import RssiHistory, RssiSample

log = logging.getLogger(__name__)

# Colors cycled by sorted adapter address index (colorblind-friendly palette)
_PALETTE = [
    QColor("#1f77b4"),
    QColor("#ff7f0e"),
    QColor("#2ca02c"),
    QColor("#d62728"),
    QColor("#9467bd"),
    QColor("#8c564b"),
]

_WINDOW_OPTIONS = [("5 min", 300), ("15 min", 900)]


class RssiPlot(QWidget):
    """QChartView showing one QLineSeries per adapter over a sliding time window."""

    def __init__(self, history: RssiHistory, monitor: AbstractBluetoothMonitor,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._history = history
        self._monitor = monitor
        self._window_s: float = 300.0
        # Parallel list of RssiSample lists for tooltip lookup, keyed by series index
        self._series_samples: list[list[RssiSample]] = []
        # Hovered series index and point index for tooltip; -1 means none
        self._hovered_series: int = -1
        self._hci_versions: dict[str, str | None] = {}

        self._chart = QChart()
        self._chart.setTitle("RSSI History")
        self._chart.legend().setAlignment(Qt.AlignmentFlag.AlignTop)
        self._chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)

        self._axis_x = QValueAxis()
        self._axis_x.setTitleText("seconds ago")
        self._axis_x.setReverse(True)
        self._axis_x.setRange(0, self._window_s)

        self._axis_y = QValueAxis()
        self._axis_y.setTitleText("RSSI (dBm)")
        self._axis_y.setRange(-100, 0)
        self._axis_y.setTickCount(11)

        self._chart.addAxis(self._axis_x, Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, Qt.AlignmentFlag.AlignLeft)

        self._view = QChartView(self._chart)
        self._view.setRenderHint(self._view.renderHints().__class__.Antialiasing)

        self._window_combo = QComboBox()
        for label, _ in _WINDOW_OPTIONS:
            self._window_combo.addItem(label)
        self._window_combo.currentIndexChanged.connect(self._on_window_changed)

        top = QHBoxLayout()
        top.addWidget(QLabel("Window:"))
        top.addWidget(self._window_combo)
        top.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._view)

        self._update_timer = QTimer(self)
        self._update_timer.setInterval(1000)
        self._update_timer.timeout.connect(self._refresh)

        monitor.adapter_rssi_updated.connect(self._on_adapter_rssi)

    def start(self) -> None:
        self._update_timer.start()
        self._refresh()

    def stop(self) -> None:
        self._update_timer.stop()

    @pyqtSlot(int)
    def _on_window_changed(self, index: int) -> None:
        self._window_s = float(_WINDOW_OPTIONS[index][1])
        self._axis_x.setRange(0, self._window_s)
        self._refresh()

    @pyqtSlot(str, int, str)
    def _on_adapter_rssi(self, adapter: str, rssi: int, source: str) -> None:
        # Eagerly cache hci_version on first sighting of each adapter
        if adapter not in self._hci_versions:
            hci_name = self._hci_name_for(adapter)
            if hci_name:
                from bluelock.bluetooth._adapters import hci_version
                self._hci_versions[adapter] = hci_version(hci_name)
            else:
                self._hci_versions[adapter] = None

    def _hci_name_for(self, adapter_address: str) -> str:
        """Return the hciN name for *adapter_address* from the bound monitor adapters."""
        if hasattr(self._monitor, "bound_adapters"):
            for info in self._monitor.bound_adapters:
                if info.address == adapter_address:
                    return info.hci_name
        return ""

    def _refresh(self) -> None:
        now = time.monotonic()
        adapters = sorted(self._history.adapters())

        # Remove series that no longer correspond to known adapters
        existing_titles = {s.name() for s in self._chart.series()}
        for title in existing_titles:
            if title not in adapters:
                for s in self._chart.series():
                    if s.name() == title:
                        self._chart.removeSeries(s)
                        break

        # Ensure one series per adapter
        series_map: dict[str, QLineSeries] = {}
        for s in self._chart.series():
            series_map[s.name()] = s  # type: ignore[assignment]

        self._series_samples = []
        for idx, addr in enumerate(adapters):
            if addr not in series_map:
                series = QLineSeries()
                series.setName(addr)
                color = _PALETTE[idx % len(_PALETTE)]
                pen = series.pen()
                pen.setColor(color)
                pen.setWidth(2)
                series.setPen(pen)
                self._chart.addSeries(series)
                series.attachAxis(self._axis_x)
                series.attachAxis(self._axis_y)
                series_map[addr] = series
                series.hovered.connect(lambda point, state, a=addr: self._on_hovered(a, point, state))
            s = series_map[addr]
            samples = self._history.samples(addr, window_s=self._window_s)
            points = [QPointF(now - sample.ts, sample.rssi) for sample in samples]
            s.replace(points)
            self._series_samples.append(samples)

    def _on_hovered(self, adapter: str, point: QPointF, state: bool) -> None:
        if not state:
            QToolTip.hideText()
            return
        adapters = sorted(self._history.adapters())
        try:
            idx = adapters.index(adapter)
        except ValueError:
            return
        if idx >= len(self._series_samples):
            return
        samples = self._series_samples[idx]
        if not samples:
            return
        # Find nearest sample by ts (point.x() is seconds_ago)
        now = time.monotonic()
        target_ts = now - point.x()
        nearest = min(samples, key=lambda s: abs(s.ts - target_ts))
        age = int(now - nearest.ts)
        ver = self._hci_versions.get(adapter)
        ver_str = f" ({ver})" if ver else ""
        hci = self._hci_name_for(adapter)
        label = hci or adapter
        tip = f"{label}{ver_str} · {nearest.rssi} dBm · {nearest.source} · {age}s ago"
        cursor_pos = self._view.mapToGlobal(self._view.chart().mapToPosition(point).toPoint())
        QToolTip.showText(cursor_pos, tip)


class RssiPlotDialog(QDialog):
    """Non-modal, single-instance dialog hosting RssiPlot."""

    def __init__(self, history: RssiHistory, monitor: AbstractBluetoothMonitor,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RSSI Graph")
        self.resize(700, 400)
        self.setWindowFlag(Qt.WindowType.Window)

        self._plot = RssiPlot(history, monitor, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot)

    def show(self) -> None:
        super().show()
        self._plot.start()

    def closeEvent(self, event) -> None:
        self._plot.stop()
        super().closeEvent(event)
