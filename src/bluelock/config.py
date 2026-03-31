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

    ``device`` holds the proximity configuration for the monitored Bluetooth device.
    """

    device: DeviceConfig | None = None
    buffer_size: int = 16
    scan_interval: float = 1.0
    rssi_method: str = "auto"

    # ------------------------------------------------------------------
    # Properties for easy access to device settings
    # ------------------------------------------------------------------

    @property
    def device_mac(self) -> str:
        return self.device.mac if self.device else ""

    @property
    def device_name(self) -> str:
        return self.device.name if self.device else ""

    @property
    def lock_rssi_threshold(self) -> int:
        return self.device.lock_rssi_threshold if self.device else -15

    @property
    def lock_duration(self) -> int:
        return self.device.lock_duration if self.device else 4

    @property
    def unlock_rssi_threshold(self) -> int:
        return self.device.unlock_rssi_threshold if self.device else -10

    @property
    def unlock_duration(self) -> int:
        return self.device.unlock_duration if self.device else 4

    @property
    def lock_command(self) -> str:
        return self.device.lock_command if self.device else ""

    @property
    def unlock_command(self) -> str:
        return self.device.unlock_command if self.device else ""

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
            rssi_method=str(advanced.get("rssi_method", "auto")),
        )

        # Current format: [device] single table with all fields
        d = data.get("device", {})
        if d.get("mac") and "lock_rssi" in d:
            cfg.device = DeviceConfig(
                mac=str(d["mac"]),
                name=str(d.get("name", "")),
                lock_rssi_threshold=int(d.get("lock_rssi", -15)),
                lock_duration=int(d.get("lock_duration", 4)),
                unlock_rssi_threshold=int(d.get("unlock_rssi", -10)),
                unlock_duration=int(d.get("unlock_duration", 4)),
                lock_command=str(d.get("lock_command", "")),
                unlock_command=str(d.get("unlock_command", "")),
            )

        # Backward compat: [[devices]] array (used in 0.3.x)
        if not cfg.device:
            devices = data.get("devices", [])
            if devices:
                d = devices[0]
                cfg.device = DeviceConfig(
                    mac=str(d.get("mac", "")),
                    name=str(d.get("name", "")),
                    lock_rssi_threshold=int(d.get("lock_rssi", -15)),
                    lock_duration=int(d.get("lock_duration", 4)),
                    unlock_rssi_threshold=int(d.get("unlock_rssi", -10)),
                    unlock_duration=int(d.get("unlock_duration", 4)),
                    lock_command=str(d.get("lock_command", "")),
                    unlock_command=str(d.get("unlock_command", "")),
                )

        # Backward compat: old [device] + [thresholds] + [commands] sections (pre-0.3)
        if not cfg.device:
            device = data.get("device", {})
            thresholds = data.get("thresholds", {})
            commands = data.get("commands", {})
            mac = str(device.get("mac", ""))
            if mac:
                cfg.device = DeviceConfig(
                    mac=mac,
                    name=str(device.get("name", "")),
                    lock_rssi_threshold=int(thresholds.get("lock_rssi", -15)),
                    lock_duration=int(thresholds.get("lock_duration", 4)),
                    unlock_rssi_threshold=int(thresholds.get("unlock_rssi", -10)),
                    unlock_duration=int(thresholds.get("unlock_duration", 4)),
                    lock_command=str(commands.get("lock", "")),
                    unlock_command=str(commands.get("unlock", "")),
                )

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
    """Serialize Config to TOML."""
    lines: list[str] = []

    lines.append("[advanced]")
    lines.append(f"buffer_size = {cfg.buffer_size}")
    lines.append(f"scan_interval = {cfg.scan_interval!r}")
    lines.append(f'rssi_method = "{_escape(cfg.rssi_method)}"')
    lines.append("")

    if cfg.device:
        lines.append("[device]")
        lines.append(f'mac = "{_escape(cfg.device.mac)}"')
        lines.append(f'name = "{_escape(cfg.device.name)}"')
        lines.append(f"lock_rssi = {cfg.device.lock_rssi_threshold}")
        lines.append(f"lock_duration = {cfg.device.lock_duration}")
        lines.append(f"unlock_rssi = {cfg.device.unlock_rssi_threshold}")
        lines.append(f"unlock_duration = {cfg.device.unlock_duration}")
        lines.append(f'lock_command = "{_escape(cfg.device.lock_command)}"')
        lines.append(f'unlock_command = "{_escape(cfg.device.unlock_command)}"')
        lines.append("")

    return "\n".join(lines)
