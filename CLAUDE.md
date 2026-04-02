# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test/Lint Commands

```bash
make test              # pytest -v
make coverage          # pytest -v --cov . --cov-report=term-missing
make lint              # ruff check src/bluelock tests
make format            # ruff format src/bluelock + ruff check --fix src/bluelock
make build             # python3 -m build
make run               # uv sync --group dev && uv run bluelock
make release V=X.Y.Z   # bump version, tag, build, bump to dev
pytest tests/test_config.py::TestConfigDefaults::test_default_values  # single test
```

## Architecture

BlueLock monitors Bluetooth device proximity to lock/unlock KDE sessions. It is a PyQt6 application using BlueZ D-Bus for Bluetooth and org.freedesktop.ScreenSaver/login1 D-Bus for session control.

### Signal Flow (RSSI → Lock/Unlock)

```
BluezDBusMonitor  ──rssi_updated──▶  app._on_rssi_updated()  ──▶  SignalProcessor (weighted moving average)
                                     app._evaluate() [on QTimer]  ──▶  ProximityStateMachine.evaluate()
                                     state transition?  ──▶  SessionLocker.lock() / unlock()
                                     state change  ──▶  ScreenSaverInhibitor.inhibit() / uninhibit()
                                                   ──▶  TrayIcon (update icon)
```

### Key Components

- **`app.py`**: Main orchestrator. Wires all components, handles single-instance D-Bus guard (`org.bluelock.App`), SIGUSR1 for self-restart after RPM update.
- **`bluetooth/_bluez_dbus.py`**: BlueZ D-Bus monitor. Subscribes to `PropertiesChanged` signals for RSSI (primary), falls back to subprocess polling via `_utils.py` (btmgmt → hcitool).
- **`bluetooth/_base.py`**: `AbstractBluetoothMonitor` — Qt signal interface that all monitors implement.
- **`bluetooth/_utils.py`**: `poll_rssi()` with `btmgmt_rssi()`/`hcitool_rssi()` subprocess wrappers. Caches tool availability; `force=True` bypasses the cache.
- **`signal_processor.py`**: Weighted moving-average ring buffer for RSSI smoothing + path-loss distance estimation.
- **`state_machine.py`**: Three-state (UNKNOWN/ACTIVE/GONE) hysteresis machine with separate lock/unlock RSSI thresholds and duration counters.
- **`session_locker.py`**: Lock via D-Bus `ScreenSaver.Lock()`, unlock via `login1.Session.Unlock()`, with fallback to custom shell commands. `ScreenSaverInhibitor` prevents idle lock while device is near.
- **`config.py`**: TOML config at `~/.config/bluelock/config.toml`. Hand-written serializer (no toml write dependency). Backward compat for pre-0.3 `[device]+[thresholds]+[commands]` format.
- **`config_dialog.py`**: Tabbed dialog (device scan table + per-device settings with live RSSI display). Connects to monitor signals for real-time feedback.
- **`tray.py`**: System tray icon with context menu. SVG icons in `src/bluelock/icons/` for 5 states.
- **`mon.py`**: Standalone CLI (`bluelock_mon`) for RSSI debugging. Supports `--method auto|btmgmt|hcitool|dbus|all`.

### D-Bus Usage

- **Bluetooth**: BlueZ `org.bluez` on system bus — adapter discovery, device properties, RSSI
- **Lock**: `org.freedesktop.ScreenSaver.Lock()` on session bus
- **Unlock**: `org.freedesktop.login1.Manager.GetSessionByPID()` → `Session.Unlock()` on system bus
- **Inhibit**: `org.freedesktop.ScreenSaver.Inhibit()`/`UnInhibit()` — uses dbus-python if available, falls back to `dbus-send` subprocess
- **Single instance**: Registers `org.bluelock.App` on session bus

## Code Conventions

- **Line length**: 120 (ruff enforced)
- **Quotes**: Double quotes (ruff format)
- **Annotations**: Every file uses `from __future__ import annotations`
- **Logging**: `log = logging.getLogger(__name__)` at module level
- **Qt patterns**: `pyqtSignal` for custom signals, `QTimer` for periodic/deferred work
- **Function calls**: Keep arguments on one line when under 120 chars; avoid splitting each parameter onto its own line
- **Ruff rules**: E, F, W, I, UP, B, C4, SIM (with E501, E111, E114, E701 ignored)
