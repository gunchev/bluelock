# BlueLock Implementation Plan

## Context

BlueLock is a KDE-targeted GUI Python application that monitors Bluetooth device proximity to automatically lock/unlock
the user's desktop session. It replaces the old [blueproximity](/home/dgunchev/dev/python/bluetooth_tests/blueproximity)
project whose GTK3 UI is broken and code has security issues (shell injection via `os.popen`, fragile `hcitool`
subprocess polling). The new design uses PyQt6 for native KDE integration, BlueZ D-Bus for event-driven RSSI monitoring,
and a clean modular architecture following the [keyclean](/home/dgunchev/github/gunchev/keyclean) project layout.

## Technology Choices

| Decision        | Choice                                     | Rationale                                                                       |
|-----------------|--------------------------------------------|---------------------------------------------------------------------------------|
| UI Framework    | **PyQt6**                                  | Fedora-packaged, native KDE look, QSystemTrayIcon built-in                      |
| Bluetooth       | **BlueZ D-Bus via PyQt6.QtDBus**           | Zero extra deps, event-driven RSSI, BLE + classic BT                            |
| Config format   | **TOML**                                   | `tomllib` in stdlib (3.11+), human-readable, custom writer avoids `tomli_w` dep |
| Linting         | **ruff**                                   | Fast, replaces pylint + autopep8, Fedora-packaged                               |
| Session locking | **D-Bus `org.freedesktop.ScreenSaver`**    | KDE-native, with configurable command fallback                                  |
| Async model     | **Qt event loop + QTimer + D-Bus signals** | No threads, no asyncio — everything runs on the Qt main loop                    |

## Project Structure

```
bluelock/
  .editorconfig              # exists
  .gitignore                 # exists
  LICENSE                    # exists
  PROMPT.md                  # exists
  README.md
  CHANGELOG.md
  pyproject.toml
  Makefile
  tox.ini
  release.py
  rpm/
    bluelock.spec.in
    bluelock.desktop
    bluelock.svg             # app icon
  resources/
    icons/
      bluelock_close.svg     # device nearby (green BT symbol)
      bluelock_far.svg       # device detected but far (yellow/orange)
      bluelock_gone.svg      # device absent (grey)
      bluelock_error.svg     # adapter error (red)
      bluelock_paused.svg    # monitoring paused
  src/
    bluelock/
      __init__.py            # __version__, __author__, __license__
      __main__.py            # entry point: from bluelock.app import main; main()
      app.py                 # BlueLockApp: QApplication setup, wires components
      config.py              # Config dataclass + TOML load/save
      signal_processor.py    # RSSI ring buffer, smoothing, distance estimation
      state_machine.py       # ProximityState enum, hysteresis logic
      session_locker.py      # D-Bus ScreenSaver + command fallback
      tray.py                # QSystemTrayIcon, context menu, icon management
      config_dialog.py       # Configuration QDialog
      about_dialog.py        # About QDialog
      bluetooth/
        __init__.py          # get_monitor() factory
        _base.py             # AbstractBluetoothMonitor (QObject ABC)
        _bluez_dbus.py       # BlueZ D-Bus implementation via QtDBus
        _types.py            # DeviceInfo, RssiReading dataclasses
  tests/
    conftest.py              # QApplication fixture, D-Bus mocks
    test_config.py
    test_signal_processor.py
    test_state_machine.py
    test_session_locker.py
```

## Module Design

### `config.py` — Configuration

```python
import dataclasses

@dataclasses.dataclass
class Config:
    device_mac: str = ""
    device_name: str = ""
    lock_rssi_threshold: int = -15  # RSSI below this = "far"
    lock_duration: int = 6  # seconds below threshold to lock
    unlock_rssi_threshold: int = -10  # RSSI above this = "close"
    unlock_duration: int = 1  # seconds above threshold to unlock
    lock_command: str = ""  # empty = use D-Bus ScreenSaver
    unlock_command: str = ""  # empty = use D-Bus ScreenSaver
    buffer_size: int = 5  # ring buffer for RSSI averaging
    scan_interval: float = 1.0  # seconds between state evaluations
```

- Location: `~/.config/bluelock/config.toml` (XDG-compliant)
- Read via `tomllib` (stdlib), write via minimal custom serializer (~20 lines)
- Sections: `[device]`, `[thresholds]`, `[commands]`, `[advanced]`

### `bluetooth/_bluez_dbus.py` — BlueZ D-Bus Monitor

Uses `PyQt6.QtDBus.QDBusConnection` to interact with BlueZ on the system bus:

- **Device scanning**: Call `Adapter1.StartDiscovery()`, listen for `InterfacesAdded` signals to find devices with
  Address/Name/RSSI
- **RSSI monitoring**: Subscribe to `PropertiesChanged` on `org.bluez.Device1` for the target MAC. BlueZ emits RSSI
  updates during active discovery.
- **Device disappearance**: Detect via `InterfacesRemoved` signal — emit `device_disconnected`
- **Fallback**: For connected classic BT devices where D-Bus RSSI isn't updated, fall back to
  `subprocess.run(["hcitool", "rssi", mac])` on a QTimer (safe, no shell)

Qt signals emitted: `rssi_updated(int)`, `device_connected(str)`, `device_disconnected()`, `scan_result(str, str)`,
`scan_finished()`, `error_occurred(str)`

### `signal_processor.py` — RSSI Smoothing

- Ring buffer (`collections.deque`) of configurable size (default 4)
- Weighted moving average for smoothed RSSI
- Distance estimation via log-distance path loss model: `d = 10^((tx_power - rssi) / (10 * n))` where
  `tx_power ≈ -59 dBm`, `n ≈ 2.5` (indoor)
- Properties: `smoothed_rssi`, `estimated_distance_m`, `last_raw`

### `state_machine.py` — Lock/Unlock Hysteresis

Three states: `UNKNOWN`, `ACTIVE` (unlocked), `GONE` (locked)

```
UNKNOWN → first RSSI reading → ACTIVE or GONE (no lock/unlock command executed)

ACTIVE → GONE: smoothed_rssi <= lock_threshold for lock_duration consecutive seconds
GONE → ACTIVE: smoothed_rssi >= unlock_threshold for unlock_duration consecutive seconds
```

Separate lock/unlock thresholds provide hysteresis — prevents oscillation when signal hovers near a single value.
Duration counters reset when condition stops being met.

### `session_locker.py` — Session Lock/Unlock

- **Default**: D-Bus call to `org.freedesktop.ScreenSaver.Lock()` / `.SetActive(false)` on the session bus
- **Fallback**: User-configured commands parsed via `shlex.split()`, executed via `subprocess.run(shell=False)` — no
  shell injection possible
- Signals: `lock_executed(bool)`, `unlock_executed(bool)`

### `tray.py` — System Tray Icon

- `QSystemTrayIcon` with 5 SVG icon states (close/far/gone/error/paused)
- Right-click `QMenu`: Preferences, Pause/Resume (checkable), separator, About, Help, separator, Quit
- Tooltip: device name, current RSSI, estimated distance, state
- Icon updates on each state machine evaluation (via QTimer, ~1/sec)

### `config_dialog.py` — Configuration Dialog

- **Device section**: MAC field + Scan button → QTableWidget results → "Use Selected"
- **Signal section**: Real-time RSSI display (QProgressBar), distance label, min/max
- **Lock threshold**: QSlider + QSpinBox for RSSI, QSpinBox for duration (seconds)
- **Unlock threshold**: Same layout
- **Commands**: Lock/unlock QLineEdits (empty = D-Bus default)
- **Advanced**: Buffer size, scan interval

### `app.py` — Application Coordinator

Wires everything together:

1. Load config
2. Create BluetoothMonitor, SignalProcessor, StateMachine, SessionLocker, TrayIcon
3. Connect signal chain: `monitor.rssi_updated` → `signal_processor.add_reading` → `QTimer(1s)` →
   `state_machine.evaluate` → `session_locker.lock/unlock`
4. Connect tray menu signals to config dialog, pause, quit
5. Run `QApplication.exec()`

## Dependencies

### Runtime (all Fedora-packaged RPMs)

- `python3 >= 3.11` (for `tomllib`)
- `python3-pyqt6-base` (Qt6 widgets, QtDBus, QSystemTrayIcon)
- `bluez` (BlueZ daemon)

### pyproject.toml

```toml
dependencies = ["PyQt6>=6.5.0"]
```

### Development

- `ruff` (lint + format), PEP-8 style
- `pytest`, `pytest-mock`, `pytest-cov`
- `tox`, `build`, `twine`

## Implementation Phases

### Phase 1: Project skeleton + core logic (no GUI)

1. Create `pyproject.toml`, `Makefile`, `tox.ini`, `release.py` (modeled on keyclean)
2. `src/bluelock/__init__.py`, `__main__.py`
3. `config.py` — Config dataclass with TOML load/save
4. `signal_processor.py` — ring buffer and averaging
5. `state_machine.py` — full hysteresis state machine
6. `session_locker.py` — D-Bus + command fallback
7. Tests for config, signal_processor, state_machine, session_locker

### Phase 2: Bluetooth D-Bus integration

8. `bluetooth/_types.py`, `_base.py`, `__init__.py`
9. `bluetooth/_bluez_dbus.py` — QtDBus BlueZ monitor
10. Manual testing with real Bluetooth device

### Phase 3: GUI

11. `tray.py` — system tray icon with menu
12. `config_dialog.py` — configuration dialog with real-time signal display
13. `about_dialog.py`
14. `app.py` — wire everything together
15. Create SVG icons (5 states)

### Phase 4: Polish & packaging

16. `rpm/bluelock.spec.in`, `bluelock.desktop`, app icon SVG
17. `README.md`, `CHANGELOG.md`
18. Error handling hardening, edge case testing

## Verification

1. **Unit tests**: `make test` — state machine transitions, signal processing math, config serialization, command
   parsing
2. **Manual integration**: `make run` — pair a phone, verify tray icon updates, RSSI readings display in config dialog
3. **Lock/unlock cycle**: Walk away from desk with phone → session locks after configured duration; return → session
   unlocks
4. **Edge cases**: Toggle Bluetooth adapter off/on, kill BlueZ, unpair device mid-monitoring — app should show error
   icon and recover
5. **RPM**: `make rpm` — install on clean Fedora, verify dependencies resolve, desktop entry works

## Key Files to Modify/Create

- `pyproject.toml` — new
- `Makefile` — new (based on keyclean's)
- `src/bluelock/state_machine.py` — core lock/unlock logic
- `src/bluelock/bluetooth/_bluez_dbus.py` — most complex module
- `src/bluelock/app.py` — application coordinator
- `src/bluelock/config.py` — needed by all modules
- `src/bluelock/tray.py` — user-facing tray icon

## Reusable Patterns from Existing Code

- **keyclean's `Makefile`**: Copy and adapt targets (help, check, test, coverage, lint, build, userinstall, run, rpm,
  release, clean). Replace pylint/autopep8 with ruff.
- **keyclean's `pyproject.toml`**: Same hatchling build backend, similar structure.
- **keyclean's `release.py`**: Reuse version-bump and changelog-generation logic.
- **keyclean's `tox.ini`**: Same test matrix pattern.
- **blueproximity's state machine** (`proximity.py:1337-1393`): Reference for gone/active transition logic, but
  rewritten with proper hysteresis and no threading.
- **blueproximity's icon states** (`blueproximity_*.svg`): Reference for icon design (5 states: base, attention, nocon,
  error, pause).
