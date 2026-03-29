# BlueLock

Lock and unlock your KDE desktop session based on Bluetooth device proximity.

BlueLock monitors a paired Bluetooth device's signal strength. When the device
moves out of range the session is locked automatically; when it returns the
session is unlocked.

## Features

- System tray icon with five states reflecting proximity and lock status
- Configurable RSSI thresholds with hysteresis (separate lock/unlock levels)
- Configurable time durations before acting (avoids triggering on momentary drops)
- D-Bus `org.freedesktop.ScreenSaver` for lock/unlock — no extra tools required
- Optional custom lock/unlock shell commands
- RSSI smoothing with a configurable ring buffer
- Real-time signal strength display in the configuration dialog

## Requirements

- Python 3.11+
- PyQt6 (`python3-pyqt6-base` on Fedora)
- BlueZ (`bluez`)

## Installation

### From source

```bash
pip install .
bluelock
```

### Development

```bash
make run
```

### RPM (Fedora)

```bash
make rpm
sudo rpm -i ~/rpmbuild/RPMS/noarch/bluelock-*.rpm
```

## Usage

1. Launch BlueLock — it appears in the system tray.
2. Right-click the tray icon and choose **Preferences**.
3. Click **Scan** to find nearby Bluetooth devices.
4. Select your device and click **Use**.
5. Adjust the lock/unlock RSSI thresholds and durations to taste.
6. Click **OK** — monitoring begins immediately.

### Tray icon states

| Icon                   | Meaning                                         |
|------------------------|-------------------------------------------------|
| **Close** (blue)       | Device is nearby — session is unlocked          |
| **Far** (yellow/amber) | Device is moving away — lock countdown active   |
| **Gone** (red)         | Device is absent — session is locked            |
| **Error** (grey)       | Initialising, or no signal yet                  |
| **Paused**             | Monitoring is paused — no automatic lock/unlock |

### Thresholds

| Setting         | Description                                                                 |
|-----------------|-----------------------------------------------------------------------------|
| Lock RSSI       | Session locks when signal drops **below** this level                        |
| Lock duration   | Signal must stay below the threshold for this many seconds before locking   |
| Unlock RSSI     | Session unlocks when signal rises **above** this level                      |
| Unlock duration | Signal must stay above the threshold for this many seconds before unlocking |

The gap between the lock and unlock thresholds acts as a hysteresis band,
preventing the session from oscillating when you are standing right at the
boundary.

### Configuration file

Saved at `~/.config/bluelock/config.toml`.

## Development

```bash
make test        # run tests
make coverage    # run tests with coverage report
make lint        # run ruff
make format      # auto-format with ruff
make build       # build wheel and sdist
make release V=X.Y.Z  # tag and publish a release
```

## License

[Unlicense](LICENSE) — public domain.
