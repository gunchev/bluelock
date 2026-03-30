### Project Audit: BlueLock

After examining the project structure and source code, I have identified several opportunities for bug fixes, cleanup,
and optimizations.

#### Bug Fixes & Improvements

* **D-Bus Unlock Reliability:** In `src/bluelock/session_locker.py`, the `_dbus_unlock` method uses
  `os.environ.get("XDG_SESSION_ID", "auto")`. If `XDG_SESSION_ID` is not in the environment (which can happen depending
  on how the app is started), it defaults to `auto`, but then constructs a path `/org/freedesktop/login1/session/auto`.
  This path is likely invalid. A better approach would be to use the `GetSessionByPID` method on the
  `org.freedesktop.login1.Manager` interface to find the correct session path dynamically.
* **Duplicate Code:** The functions `_btmgmt_rssi` and `_hcitool_rssi` are duplicated in `src/bluelock/mon.py` and
  `src/bluelock/bluetooth/_bluez_dbus.py`. These should be moved to a shared utility module (e.g.,
  `src/bluelock/bluetooth/_utils.py`) to ensure consistency and easier maintenance.
* **Configuration Logic:** In `src/bluelock/config.py`, the `Config` class uses "shims" (properties) that delegate only
  to the first device in the `devices` list. While this maintains backward compatibility with the rest of the app, the
  UI allows for multiple device tabs. If a user expects to monitor multiple devices, the current implementation will
  ignore all but the first one. The app should either explicitly support multiple devices or the UI should be restricted
  to a single device.
* **Resource Management:** In `src/bluelock/app.py`, when a new configuration is applied in `_apply_config`, the
  previous `ProximityStateMachine` is replaced, but the old one doesn't have any resources to clean up. However, the
  `_monitor.stop_monitoring()` is called, which is correct.

#### Optimization Opportunities

* **RSSI Polling Efficiency:** `BluezDBusMonitor` in `src/bluelock/bluetooth/_bluez_dbus.py` uses a 2-second timer (
  `_RSSI_POLL_MS`) to fallback to `btmgmt` or `hcitool`. This polling is performed even if D-Bus is providing regular
  `RSSI` updates via `PropertiesChanged`. It could be optimized to only poll if no D-Bus updates have been received for
  a certain period.
* **Process Spawning:** Polling RSSI via `subprocess.run(["sudo", "btmgmt", ...])` every 2 seconds is relatively
  expensive. While necessary for some "classic" Bluetooth devices that don't emit RSSI updates while connected, it
  should be used sparingly.

#### Cleanup & Maintenance

* **Unused Imports and Declarations:** `src/bluelock/mon.py` is a standalone script that duplicates much of the logic in
  the main package. It seems to be used for debugging. It should be refactored to use the core library components to
  avoid logic drift.
* **Icon Consistency:** There is a duplication of icons between `resources/icons` and `src/bluelock/icons`. The package
  should use a single source for these assets, preferably managed by `hatchling` during the build process.
* **Error Handling:** In `src/bluelock/bluetooth/_bluez_dbus.py`, many D-Bus calls check for error replies but only log
  them. In some cases, these errors should be propagated back to the user via the `error_occurred` signal more
  consistently.
* **Type Hinting:** While generally good, some methods like `ConfigDialog.__init__` in `src/bluelock/config_dialog.py`
  are missing type hints for some parameters (e.g., `parent`).

#### Summary of Recommendations

1. **Refactor `SessionLocker._dbus_unlock`** to use `GetSessionByPID` for more robust session detection.
2. **Consolidate Bluetooth utility functions** into a single module to eliminate code duplication.
3. **Optimize the fallback polling logic** in `BluezDBusMonitor` to reduce unnecessary subprocess calls.
4. **Unify icon resources** to prevent asset duplication and potential sync issues.
5. **Clean up `src/bluelock/mon.py`** to use the shared monitoring logic.
