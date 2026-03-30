#!/usr/bin/env python3
"""Test script for ScreenSaverInhibitor.

Run with: python3 test_inhibitor.py   (needs system dbus-python / dbus-send)

Calls inhibit(), waits 5 s, then uninhibit() twice to verify the cookie is released.
Watch the screensaver settings while it runs — inhibition should be visible in
System Settings → Screen Locking while the script sleeps.
"""
from __future__ import annotations

import sys
import sysconfig
import time

# Use system site-packages so dbus-python is found (not available in the uv venv)
sys.path.insert(0, sysconfig.get_path('platlib'))

from PyQt6.QtCore import QCoreApplication, QTimer

# Make the bluelock src importable
sys.path.insert(0, 'src')
from bluelock.session_locker import ScreenSaverInhibitor


def run_test() -> None:
    inh = ScreenSaverInhibitor()
    print(f"active before inhibit: {inh.active}")

    print("\n--- inhibit() ---")
    inh.inhibit()
    print(f"active after inhibit:  {inh.active}")

    print("\nSleeping 5s (screensaver should be inhibited now)…")
    time.sleep(5)

    print("\n--- uninhibit() ---")
    inh.uninhibit()
    print(f"active after uninhibit: {inh.active}")

    print("\n--- second uninhibit() (should be no-op) ---")
    inh.uninhibit()
    print(f"active (still):        {inh.active}")

    print("\n--- inhibit again (second cycle) ---")
    inh.inhibit()
    print(f"active:                {inh.active}")
    time.sleep(3)
    inh.uninhibit()
    print(f"active after 2nd uninhibit: {inh.active}")

    print("\nDone.")
    QCoreApplication.instance().quit()


def main() -> None:
    app = QCoreApplication(sys.argv)
    QTimer.singleShot(0, run_test)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
