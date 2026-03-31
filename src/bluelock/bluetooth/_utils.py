"""Bluetooth utility functions."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)

RSSI_METHODS = ("auto", "dbus", "btmgmt", "hcitool")

_btmgmt_available = True
_hcitool_available = True


def btmgmt_rssi(mac: str, *, force: bool = False) -> tuple[int | None, str]:
    """Read live RSSI via 'btmgmt conn-info' (requires CAP_NET_ADMIN / bluetooth group / sudo).

    When *force* is True the availability cache is bypassed and not updated,
    so a single forced call cannot permanently disable auto-detect mode.
    """
    global _btmgmt_available
    if not _btmgmt_available and not force:
        return None, "btmgmt not available"
    try:
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
        if not force and result.returncode == 1 and "sudo: a password is required" in output:
            log.warning("btmgmt: sudo password required, disabling btmgmt polling")
            _btmgmt_available = False
        return None, (output.splitlines()[-1] if output else f"exit {result.returncode}")[:60]
    except FileNotFoundError:
        if not force:
            log.warning("btmgmt not found, disabling btmgmt polling")
            _btmgmt_available = False
        return None, "btmgmt not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def hcitool_rssi(mac: str, *, force: bool = False) -> tuple[int | None, str]:
    """Read RSSI via 'hcitool rssi' (deprecated fallback, part of bluez-deprecated).

    When *force* is True the availability cache is bypassed and not updated.
    """
    global _hcitool_available
    if not _hcitool_available and not force:
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
        if not force:
            log.warning("hcitool not found, disabling hcitool polling")
            _hcitool_available = False
        return None, "hcitool not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def poll_rssi(mac: str, method: str = "auto") -> tuple[int | None, str, str]:
    """Poll RSSI using the specified method.

    Returns ``(rssi_or_None, error_message, tool_name)``.

    For ``"btmgmt"`` or ``"hcitool"``, forces that specific tool and bypasses
    the availability cache so a previously disabled tool can be retried.
    For ``"auto"``, tries btmgmt then hcitool with normal availability caching.
    """
    if method == "btmgmt":
        rssi, err = btmgmt_rssi(mac, force=True)
        return rssi, err, "btmgmt"
    if method == "hcitool":
        rssi, err = hcitool_rssi(mac, force=True)
        return rssi, err, "hcitool"
    # auto: btmgmt first, hcitool fallback
    rssi, err = btmgmt_rssi(mac)
    if rssi is not None:
        return rssi, err, "btmgmt"
    rssi, err = hcitool_rssi(mac)
    return rssi, err, "hcitool"
