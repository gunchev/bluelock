"""Bluetooth utility functions."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


def btmgmt_rssi(mac: str) -> tuple[int | None, str]:
    """Read live RSSI via 'btmgmt conn-info' (requires CAP_NET_ADMIN / bluetooth group / sudo)."""
    try:
        # We use 'sudo -n' to fail immediately if password is required
        result = subprocess.run(["sudo", "-n", "btmgmt", "conn-info", mac, "BR/EDR"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            parts = result.stdout.split()
            for i, part in enumerate(parts):
                if part == "rssi" and i + 1 < len(parts):
                    try:
                        val = int(parts[i + 1])
                        if -120 <= val <= 20:
                            return val, ""
                    except ValueError:
                        pass
        output = (result.stdout + result.stderr).strip()
        return None, (output.splitlines()[-1] if output else f"exit {result.returncode}")[:60]
    except FileNotFoundError:
        return None, "btmgmt not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def hcitool_rssi(mac: str) -> tuple[int | None, str]:
    """Read RSSI via 'hcitool rssi' (deprecated fallback, part of bluez-deprecated)."""
    try:
        result = subprocess.run(["hcitool", "rssi", mac], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            for part in result.stdout.split():
                try:
                    val = int(part)
                    if -120 <= val <= 20:
                        return val, ""
                except ValueError:
                    pass
        output = (result.stdout + result.stderr).strip()
        return None, (output or f"exit {result.returncode}")[:60]
    except FileNotFoundError:
        return None, "hcitool not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)
