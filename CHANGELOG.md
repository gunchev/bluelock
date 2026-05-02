## 0.5.0 — 2026-05-03

### Changes since v0.4.2

- 4b0b0de Narrow OSError catch to FileNotFoundError in config.load()
- 9fb7c56 Let config parse errors propagate; log and fall back in app.py
- 41ce2b1 Skip state evaluation in app._evaluate() when device present but no readings
- 1d6ede1 Skip UNKNOWN→GONE transition when device present but no readings yet
- 89707c8 Fall back to defaults on type conversion errors in config.load()
- 386636f Fix autostart path to respect XDG_CONFIG_HOME
- eaf1ceb MiniMax M2.5 Free OpenCode Zen removes bogus bug.
- 69c0c64 Bugs by Hy3 preview Free OpenCode Zen
- 8cec2a9 Drop solved bugs.
- dad1499 Update BUGS.md: mark three bugs fixed, annotate zombie-state bug
- 6a8e5f5 Resolve SIGUSR1 re-exec path via shutil.which with module fallback
- 3cd10d6 Store sentinel cookie 0 when dbus-send inhibit output is unparseable
- 85a54d9 Return (resolved, missing) tuple from resolve_addresses
- 0f5e2a8 Distinguish BlueZ-not-running from other GetManagedObjects failures
- 426e5ad Retry StartDiscovery on NotPowered in addition to NotReady
- 24415b6 Raise log level for missing configured adapters from INFO to WARNING
- d93a329 Document get_known_devices deduplication by MAC limitation
- eb16e54 Document that start_scan scans all adapters regardless of selection
- 849a873 Replace linear scan in _adapter_address_for_device_path with O(1) dict
- 3125bf9 Fix stale AdapterInfo.powered after power toggle
- e331b6e Fix unpowered adapter never re-binds when powered on
- f30dd59 Multiadapter PR3
- 4cdf158 MultiAdapter PR2
- c804fa6 Multiadapter PR1

## 0.4.2 — 2026-04-11

### Changes since v0.4.1

- e355356 Missing deps, sync release.py
- b7d17ef Start 0.4.2-dev

## 0.4.2 — 2026-04-11

### Changes since v0.4.1

- d489c29 Missing deps, sync release.py
- b7d17ef Start 0.4.2-dev

## 0.4.1 — 2026-04-11

### Changes since v0.4.0

- 09c64f6 COPR integration...
- 6281a6d Start 0.4.1-dev

## 0.4.0 — 2026-04-03

### Changes since v0.3.6

- c52b53a Code review fixes: sync version, remove unused code, fix empty test
- 24ecfef Start 0.3.7-dev

## 0.3.6 — 2026-04-03

### Changes since v0.3.5

- d39cd50 Clean up lint issues, remove dead code, fix ruff config placement
- 12195ce Start 0.3.6-dev

## 0.3.5 — 2026-03-31

### Changes since v0.3.4

- 1221f2b Update PROMPT.md with prompts 67-68
- 7bd01c2 Restart running instance after RPM update via SIGUSR1
- e055a78 Start 0.3.5-dev

## 0.3.4 — 2026-03-31

### Changes since v0.3.3

- 9430a22 Add Force D-Bus RSSI method; update PROMPT.md
- 62d4735 Add RSSI method override (auto/btmgmt/hcitool); bluelock_mon --method all
- a16207e Simplify test_inhibitor.py now that dbus-python is in the venv
- 9715d72 Add dbus-python as a project dependency
- 6891cb9 Start 0.3.4-dev

## 0.3.3 — 2026-03-31

### Changes since v0.3.2

- 3c9382a Increase config dialog minimum height to avoid scroll bars
- d3c77e6 Start 0.3.3-dev

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
