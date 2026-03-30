"""Configuration dataclass with TOML load/save."""
from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path


@dataclasses.dataclass
class DeviceConfig:
    """Per-device proximity configuration."""

    mac: str
    name: str = ""
    lock_rssi_threshold: int = -15
    lock_duration: int = 4
    unlock_rssi_threshold: int = -10
    unlock_duration: int = 4
    lock_command: str = ""
    unlock_command: str = ""


@dataclasses.dataclass
class Config:
    """BlueLock configuration.

    ``devices`` holds up to four DeviceConfig entries; devices[0] is the
    primary device that is currently monitored.  The shim properties below
    delegate to devices[0] so that the rest of the app (app.py, session_locker)
    does not need to know about the list.
    """

    devices: list[DeviceConfig] = dataclasses.field(default_factory=list)
    buffer_size: int = 16
    scan_interval: float = 1.0

    # ------------------------------------------------------------------
    # Shims — delegate to devices[0] so app.py needs no changes
    # ------------------------------------------------------------------

    @property
    def device_mac(self) -> str:
        return self.devices[0].mac if self.devices else ""

    @property
    def device_name(self) -> str:
        return self.devices[0].name if self.devices else ""

    @property
    def lock_rssi_threshold(self) -> int:
        return self.devices[0].lock_rssi_threshold if self.devices else -15

    @property
    def lock_duration(self) -> int:
        return self.devices[0].lock_duration if self.devices else 4

    @property
    def unlock_rssi_threshold(self) -> int:
        return self.devices[0].unlock_rssi_threshold if self.devices else -10

    @property
    def unlock_duration(self) -> int:
        return self.devices[0].unlock_duration if self.devices else 4

    @property
    def lock_command(self) -> str:
        return self.devices[0].lock_command if self.devices else ""

    @property
    def unlock_command(self) -> str:
        return self.devices[0].unlock_command if self.devices else ""

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file, returning defaults if file is missing or corrupt."""
        if path is None:
            path = cls.config_path()
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            return cls()

        advanced = data.get("advanced", {})
        cfg = cls(
            buffer_size=int(advanced.get("buffer_size", 16)),
            scan_interval=float(advanced.get("scan_interval", 1.0)),
        )

        # New format: [[devices]] array of tables
        for d in data.get("devices", []):
            cfg.devices.append(DeviceConfig(
                mac=str(d.get("mac", "")),
                name=str(d.get("name", "")),
                lock_rssi_threshold=int(d.get("lock_rssi", -15)),
                lock_duration=int(d.get("lock_duration", 4)),
                unlock_rssi_threshold=int(d.get("unlock_rssi", -10)),
                unlock_duration=int(d.get("unlock_duration", 4)),
                lock_command=str(d.get("lock_command", "")),
                unlock_command=str(d.get("unlock_command", "")),
            ))

        # Backward compat: old [device] / [thresholds] / [commands] sections
        if not cfg.devices:
            device = data.get("device", {})
            thresholds = data.get("thresholds", {})
            commands = data.get("commands", {})
            mac = str(device.get("mac", ""))
            if mac:
                cfg.devices.append(DeviceConfig(
                    mac=mac,
                    name=str(device.get("name", "")),
                    lock_rssi_threshold=int(thresholds.get("lock_rssi", -15)),
                    lock_duration=int(thresholds.get("lock_duration", 4)),
                    unlock_rssi_threshold=int(thresholds.get("unlock_rssi", -10)),
                    unlock_duration=int(thresholds.get("unlock_duration", 4)),
                    lock_command=str(commands.get("lock", "")),
                    unlock_command=str(commands.get("unlock", "")),
                ))

        return cfg

    def save(self, path: Path | None = None) -> None:
        """Save config to TOML file, creating the directory if needed."""
        if path is None:
            path = self.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_to_toml(self))


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _to_toml(cfg: Config) -> str:
    """Serialize Config to TOML with [[devices]] array-of-tables."""
    lines: list[str] = []

    lines.append("[advanced]")
    lines.append(f"buffer_size = {cfg.buffer_size}")
    lines.append(f"scan_interval = {cfg.scan_interval!r}")
    lines.append("")

    for dev in cfg.devices:
        lines.append("[[devices]]")
        lines.append(f'mac = "{_escape(dev.mac)}"')
        lines.append(f'name = "{_escape(dev.name)}"')
        lines.append(f"lock_rssi = {dev.lock_rssi_threshold}")
        lines.append(f"lock_duration = {dev.lock_duration}")
        lines.append(f"unlock_rssi = {dev.unlock_rssi_threshold}")
        lines.append(f"unlock_duration = {dev.unlock_duration}")
        lines.append(f'lock_command = "{_escape(dev.lock_command)}"')
        lines.append(f'unlock_command = "{_escape(dev.unlock_command)}"')
        lines.append("")

    return "\n".join(lines)
