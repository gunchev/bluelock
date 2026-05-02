# Bugs

## Open

### Medium

#### `start_monitoring` leaves zombie state on invalid MAC

- **File:** `src/bluelock/bluetooth/_bluez_dbus.py`
- **Lines:** `103-119`

`_monitoring` is set to `True` at line 113 *before* the MAC validation at line 104-106. If the
MAC is invalid, an error is emitted and the method returns, but `_monitoring` stays `True` with
no adapters bound, no timer running, and no D-Bus subscriptions. A subsequent `start_monitoring`
call can't recover because `stop_monitoring()` is a no-op when `_adapter_states` is empty.

**Note:** In the current code the MAC validation at lines 104-106 already precedes
`self._monitoring = True` at line 113, so this zombie state may no longer be reachable.
Needs verification before fixing.

**Fix:** Move the `self._monitoring = True` assignment below the MAC validation guard, or reset it
on the early return.

### Low

#### `get_known_devices` deduplicates by MAC only

- **File:** `src/bluelock/bluetooth/_bluez_dbus.py`
- **Lines:** `570-598`

If the same device is visible on multiple adapters, only the first occurrence is reported. The
`DeviceInfo` type has no adapter field, so per-adapter device visibility is lost. Not a bug but
a limitation if per-adapter device discovery is ever needed. Documented in the docstring.



## Fixed

### Unpowered adapter never re-binds when powered on

- **Status:** Fixed
- **Fix:** `_adapter_path_to_address` cache (`_bluez_dbus.py:77`) populated at monitoring start
  by `_start_adapter_watching()` (`_bluez_dbus.py:376-387`). `_on_adapter_props_changed` now
  resolves the address from the cache and passes it to `_handle_powered`
  (`_bluez_dbus.py:477-478`). Tested by `test_powered_on_signal_rebinds_via_cache`
  (`tests/test_monitor_hotplug.py:107-119`) which exercises the real signal handler path.

### `_adapter_address_for_device_path` uses linear scan

- **Status:** Fixed
- **Fix:** Replaced O(n) scan with O(1) `_device_path_to_addr` dict lookup
  (`_bluez_dbus.py:445-447`). The reverse index is maintained alongside `_adapter_states`
  and updated on bind/unbind and in `_on_interfaces_added`.

### Frozen `AdapterInfo` means `powered` state is stale after power toggle

- **Status:** Fixed
- **Fix:** `_handle_powered` now uses `dataclasses.replace(state.info, powered=True)` to create
  a new `AdapterInfo` with the updated field (`_bluez_dbus.py:338`). `bound_adapters` now
  reflects the current power state.

### `_start_discovery` retry only handles `NotReady`

- **Status:** Fixed
- **Fix:** Retry condition now also covers `NotPowered` errors
  (`_bluez_dbus.py:408`), handling transient adapter initialization races.

### No D-Bus error granularity in `list_adapters`

- **Status:** Partially fixed
- **Fix:** Logging now distinguishes "BlueZ not running" (ServiceUnknown/NoReply) from other
  failures (`_adapters.py:82-85`). Callers still receive `[]` in both cases, so programmatic
  differentiation is not yet possible.

### Missing adapters silently dropped in `resolve_addresses`

- **Status:** Fixed
- **Fix:** `resolve_addresses` now returns `(resolved, missing)` — a tuple of matched
  `AdapterInfo` objects and a list of normalised MAC strings for configured-but-absent adapters
  (`_adapters.py`). The single internal call site in `_bluez_dbus.py` unpacks the tuple.

### `ScreenSaverInhibitor._inhibit_subprocess` silent failure on bad cookie

- **Status:** Fixed
- **Fix:** Stores sentinel `0` in `_cookie` when `dbus-send` succeeds but the cookie can't be
  parsed (`session_locker.py:228`). This makes `active` return `True` (preventing duplicate
  inhibit calls) and ensures `uninhibit()` fires to reset state; the resulting `UnInhibit(0)`
  call fails harmlessly on the KDE side.

### `SIGUSR1` self-restart uses `sys.argv[0]`

- **Status:** Fixed
- **Fix:** `_restart()` now calls `shutil.which(sys.argv[0])` first (resolves symlinks and PATH
  lookups for installed entry points) and falls back to `sys.executable -m bluelock` for
  module-based invocations (`app.py`).
