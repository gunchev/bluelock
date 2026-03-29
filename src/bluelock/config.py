"""Configuration dataclass with TOML load/save."""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path


@dataclasses.dataclass
class Config:
    """BlueLock configuration."""

    device_mac: str = ""
    device_name: str = ""
    lock_rssi_threshold: int = -15     # lock when RSSI drops below this (dBm)
    lock_duration: int = 4             # seconds below threshold before locking
    unlock_rssi_threshold: int = -10   # unlock when RSSI rises above this (dBm)
    unlock_duration: int = 4           # seconds above threshold before unlocking
    lock_command: str = ""             # empty = use D-Bus ScreenSaver
    unlock_command: str = ""           # empty = use D-Bus ScreenSaver
    buffer_size: int = 16              # ring buffer size for RSSI averaging
    scan_interval: float = 1.0         # seconds between state evaluations

    @staticmethod
    def config_dir() -> Path:
        """Return the XDG config directory for bluelock."""
        import os
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if xdg else Path.home() / ".config"
        return base / "bluelock"

    @staticmethod
    def config_path() -> Path:
        """Return the full path to the config file."""
        return Config.config_dir() / "config.toml"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file, returning defaults if file is missing or corrupt."""
        if path is None:
            path = cls.config_path()
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            return cls()

        device = data.get("device", {})
        thresholds = data.get("thresholds", {})
        commands = data.get("commands", {})
        advanced = data.get("advanced", {})

        return cls(
            device_mac=str(device.get("mac", "")),
            device_name=str(device.get("name", "")),
            lock_rssi_threshold=int(thresholds.get("lock_rssi", -15)),
            lock_duration=int(thresholds.get("lock_duration", 4)),
            unlock_rssi_threshold=int(thresholds.get("unlock_rssi", -10)),
            unlock_duration=int(thresholds.get("unlock_duration", 4)),
            lock_command=str(commands.get("lock", "")),
            unlock_command=str(commands.get("unlock", "")),
            buffer_size=int(advanced.get("buffer_size", 16)),
            scan_interval=float(advanced.get("scan_interval", 1.0)),
        )

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file, creating the directory if needed."""
        if path is None:
            path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_to_toml({
            "device": {
                "mac": self.device_mac,
                "name": self.device_name,
            },
            "thresholds": {
                "lock_rssi": self.lock_rssi_threshold,
                "lock_duration": self.lock_duration,
                "unlock_rssi": self.unlock_rssi_threshold,
                "unlock_duration": self.unlock_duration,
            },
            "commands": {
                "lock": self.lock_command,
                "unlock": self.unlock_command,
            },
            "advanced": {
                "buffer_size": self.buffer_size,
                "scan_interval": self.scan_interval,
            },
        }))


def _to_toml(data: dict) -> str:
    """Serialize a flat/one-level-nested dict to TOML format."""
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            if isinstance(val, bool):
                lines.append(f"{key} = {'true' if val else 'false'}")
            elif isinstance(val, str):
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            elif isinstance(val, float):
                lines.append(f"{key} = {val!r}")
            else:
                lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)
