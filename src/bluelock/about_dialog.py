"""About dialog."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from bluelock import __author__, __license__, __version__

_ABOUT_TEXT = f"""<h2>BlueLock {__version__}</h2>
<p>Lock and unlock your KDE session based on Bluetooth device proximity.</p>
<p>Author: {__author__}<br>
License: {__license__}</p>
<p>Developed with assistance from Claude and Junnie (AI assistants).</p>
<p>Monitors a paired Bluetooth device's signal strength. When the device
moves out of range, the session is locked automatically. When it returns,
the session is unlocked.</p>
"""


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About BlueLock")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        label = QLabel(_ABOUT_TEXT)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
