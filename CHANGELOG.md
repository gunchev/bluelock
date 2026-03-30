## 0.3.2 — 2026-03-31

### Changes since v0.3.1

- d0493d3 Remove redundant resources/icons/ directory
- 7ce9918 Fix RPM icon loading and add single-instance guard
- 9729549 Start 0.3.2-dev

## 0.3.1 — 2026-03-31

### Changes since v0.3.0

- afa29e0 Fix three post-Junie bugs; add ScreenSaverInhibitor unit tests
- cea66fe Restore ScreenSaverInhibitor using dbus-python with dbus-send fallback
- 7023177 Remove ScreenSaverInhibitor; add timestamps to log output
- 143179a Replace Inhibit/UnInhibit with SimulateUserActivity for screensaver suppression
- 95fe608 Fix ScreenSaverInhibitor.uninhibit() uint32 type mismatch
- 7a3b263 Minor adjustments.
- d2868a6 Add credit to Claude and Junnie in the about dialog
- e1f9df0 Cache tool availability and add mode-switching logging
- cb72fe3 Update RPM spec to include shared icon data
- fc2a81b Start 0.3.1-dev

## 0.3.0 — 2026-03-30

### Changes since v0.2.0

- 7d7ee02 Apply pending changes before release
- 8d9ff06 Update PROMPT.md with latest prompts
- a276aa7 Add type hints to ConfigDialog and _DeviceTab
- 9a204c6 Update tests to match new D-Bus unlock and Config structure
- ba1b2d2 Refactor src/bluelock/mon.py to use the shared monitoring logic
- e5c29b1 Unify icon resources and configure hatchling shared-data
- 9b65e33 Consolidate RSSI polling logic and optimize fallback polling
- 3873a59 Refactor SessionLocker._dbus_unlock to use GetSessionByPID
- 408bc76 Update PROMPT.md with prompts 38-43
- ee8c698 Rename dialog tabs to "Devices" and "Settings"
- 15f0332 Move Advanced settings to device tab; disable autostart without device
- 9c78bce Single device: lock Device tab when configured, unlock on Forget
- e9ea6de Fix RSSI display: only update the monitored device's tab
- 1ebb46c Multi-device config: per-device tabs named by MAC, up to 4 devices

## 0.1.0 — 2026-03-29

### Changes since v0.0.2

- c1fe2b5 Add autostart checkbox, bump dialog height, update PROMPT.md
- 715a10b Fix lock/unlock, add far icon state, improve UX
- 94b4217 Fix RSSI monitoring and improve config dialog UX
- c99c3c2 Fix Ctrl+C ignored while initial preferences dialog is open
- 39188e4 Fix Ctrl+C being ignored in Qt event loop
- b65a749 Start 0.0.3-dev

## 0.0.2 — 2026-03-29

### Changes since v0.0.1

- 29ff323 Fix icon path and D-Bus slot decorators

# Changelog

## 0.0.1 — 2026-03-29

Initial release. Core monitoring engine, BlueZ D-Bus integration, PyQt6 system
tray UI, configuration dialog, RPM packaging.
