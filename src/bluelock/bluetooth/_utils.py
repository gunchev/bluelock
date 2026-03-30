"""Bluetooth utility functions."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


_btmgmt_available = True
_hcitool_available = True


def btmgmt_rssi(mac: str) -> tuple[int | None, str]:
    """Read live RSSI via 'btmgmt conn-info' (requires CAP_NET_ADMIN / bluetooth group / sudo)."""
    global _btmgmt_available
    if not _btmgmt_available:
        return None, "btmgmt not available"
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
        if result.returncode == 1 and "sudo: a password is required" in output:
            log.warning("btmgmt: sudo password required, disabling btmgmt polling")
            _btmgmt_available = False
        return None, (output.splitlines()[-1] if output else f"exit {result.returncode}")[:60]
    except FileNotFoundError:
        log.warning("btmgmt not found, disabling btmgmt polling")
        _btmgmt_available = False
        return None, "btmgmt not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def hcitool_rssi(mac: str) -> tuple[int | None, str]:
    """Read RSSI via 'hcitool rssi' (deprecated fallback, part of bluez-deprecated)."""
    global _hcitool_available
    if not _hcitool_available:
        return None, "hcitool not available"
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
        log.warning("hcitool not found, disabling hcitool polling")
        _hcitool_available = False
        return None, "hcitool not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)
