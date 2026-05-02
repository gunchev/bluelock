# Bugs

## Open

### Low

#### `get_known_devices` deduplicates by MAC only

- **File:** `src/bluelock/bluetooth/_bluez_dbus.py`
- **Lines:** `570-598`

If the same device is visible on multiple adapters, only the first occurrence is reported. The
`DeviceInfo` type has no adapter field, so per-adapter device visibility is lost. Not a bug but
a limitation if per-adapter device discovery is ever needed. Documented in the docstring.
