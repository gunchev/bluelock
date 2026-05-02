# Bugs

## Open

### High

#### `config.py: load()` doesn't handle type conversion errors

- **File:** `src/bluelock/config.py`
- **Lines:** `98-150`

The `try` block only covers `tomllib.loads(path.read_text())`. If the TOML file contains
invalid types (e.g., `buffer_size = "abc"`), the `int()` conversions on lines 110-128
will raise `ValueError`, which is not caught. This crashes the application instead of
falling back to defaults.

**Fix:** Extend the `try` block to cover the entire method body, or add `ValueError` to
the caught exception types.

#### Initial state determined without RSSI readings

- **File:** `src/bluelock/state_machine.py`
- **Lines:** `81-88` (`_handle_unknown`), `71-72` (`evaluate`)

When the state machine is in UNKNOWN state, `_handle_unknown()` determines the initial
state based on `effective_rssi`. If no RSSI readings have been received yet,
`smoothed_rssi` returns `NO_SIGNAL` (-127), causing the initial state to be GONE even
if the device is actually nearby. The device then needs `unlock_duration` seconds of
good RSSI to transition back to ACTIVE, causing a spurious lock period after startup.

**Fix:** Skip evaluation when `smoothed_rssi` is `NO_SIGNAL` and `device_present` is True,
or wait for the first RSSI reading before determining the initial state.

### Medium

#### `app.py` evaluates state with empty RSSI buffer

- **File:** `src/bluelock/app.py`
- **Lines:** `88-110` (`_evaluate`)

`_evaluate()` calls `self._machine.evaluate(self._processor.smoothed_rssi, self._device_present)`
without checking if there are any RSSI readings. If the buffer is empty, `smoothed_rssi`
returns `NO_SIGNAL` (-127). Combined with `device_present=True` (device appeared but
no reading yet), this makes `effective_rssi = -127.0`, which may trigger incorrect
state transitions.

**Fix:** Check `self._processor.has_readings` before calling `evaluate()`, or let
the state machine handle the NO_SIGNAL case specially when `device_present` is True.

#### `config.py` TOML key inconsistency

- **File:** `src/bluelock/config.py`
- **Lines:** `123, 178` (lock_rssi), `125, 180` (unlock_rssi)

The TOML file uses short keys (`lock_rssi`, `unlock_rssi`) but the `DeviceConfig`
fields are named `lock_rssi_threshold`, `unlock_rssi_threshold`. While the load/save
functions handle the mapping correctly, manually edited TOML files using the Python
field names won't be parsed correctly.

### Low

#### `get_known_devices` deduplicates by MAC only

- **File:** `src/bluelock/bluetooth/_bluez_dbus.py`
- **Lines:** `570-598`

If the same device is visible on multiple adapters, only the first occurrence is reported. The
`DeviceInfo` type has no adapter field, so per-adapter device visibility is lost. Not a bug but
a limitation if per-adapter device discovery is ever needed. Documented in the docstring.

#### `config_dialog.py` autostart file path doesn't respect XDG_CONFIG_HOME

- **File:** `src/bluelock/config_dialog.py`
- **Lines:** `43`

`_AUTOSTART_FILE = Path.home() / ".config" / "autostart" / "bluelock.desktop"`
hardcodes `~/.config`. The XDG spec says autostart files should be in
`$XDG_CONFIG_HOME/autostart/`. While most users use the default, this ignores
the XDG_CONFIG_HOME environment variable.

**Note:** `config.py` correctly uses `XDG_CONFIG_HOME` for the config file itself.
