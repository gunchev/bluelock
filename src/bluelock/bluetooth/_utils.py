"""Bluetooth utility functions."""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)

RSSI_METHODS = ("auto", "dbus", "btmgmt", "hcitool")

# Per-adapter availability caches. Key: adapter name ("hci0", ...) or None for
# "no adapter specified". Missing key ⇒ assume available. A bad dongle on hci1
# must not disable polling for hci0.
_btmgmt_available: dict[str | None, bool] = {}
_hcitool_available: dict[str | None, bool] = {}


def _available(cache: dict[str | None, bool], adapter: str | None) -> bool:
    return cache.get(adapter, True)


def btmgmt_rssi(mac: str, *, adapter: str | None = None, force: bool = False) -> tuple[int | None, str]:
    """Read live RSSI via 'btmgmt conn-info' (requires CAP_NET_ADMIN / bluetooth group / sudo).

    *adapter* selects a specific controller (e.g. ``"hci0"``); ``None`` lets btmgmt
    pick its default. When *force* is True the availability cache is bypassed and
    not updated, so a single forced call cannot permanently disable auto-detect mode.
    """
    if not force and not _available(_btmgmt_available, adapter):
        return None, "btmgmt not available"
    cmd = ["sudo", "-n", "btmgmt"]
    if adapter:
        cmd += ["-i", adapter]
    cmd += ["conn-info", mac, "BR/EDR"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
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
            log.warning("btmgmt[%s]: sudo password required, disabling btmgmt polling", adapter or "default")
            _btmgmt_available[adapter] = False
        return None, (output.splitlines()[-1] if output else f"exit {result.returncode}")[:60]
    except FileNotFoundError:
        if not force:
            log.warning("btmgmt not found, disabling btmgmt polling")
            _btmgmt_available[adapter] = False
        return None, "btmgmt not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def hcitool_rssi(mac: str, *, adapter: str | None = None, force: bool = False) -> tuple[int | None, str]:
    """Read RSSI via 'hcitool rssi' (deprecated fallback, part of bluez-deprecated).

    *adapter* selects a specific controller (e.g. ``"hci0"``). When *force* is True
    the availability cache is bypassed and not updated.
    """
    if not force and not _available(_hcitool_available, adapter):
        return None, "hcitool not available"
    cmd = ["hcitool"]
    if adapter:
        cmd += ["-i", adapter]
    cmd += ["rssi", mac]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
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
            _hcitool_available[adapter] = False
        return None, "hcitool not found"
    except (subprocess.TimeoutExpired, OSError) as e:
        return None, str(e)


def poll_rssi(mac: str, method: str = "auto", adapter: str | None = None) -> tuple[int | None, str, str]:
    """Poll RSSI using the specified method.

    Returns ``(rssi_or_None, error_message, tool_name)``.

    For ``"btmgmt"`` or ``"hcitool"``, forces that specific tool and bypasses
    the availability cache so a previously disabled tool can be retried.
    For ``"auto"``, tries btmgmt then hcitool with normal availability caching.
    *adapter* (e.g. ``"hci0"``) is forwarded to the underlying tool.
    """
    if method == "btmgmt":
        rssi, err = btmgmt_rssi(mac, adapter=adapter, force=True)
        return rssi, err, "btmgmt"
    if method == "hcitool":
        rssi, err = hcitool_rssi(mac, adapter=adapter, force=True)
        return rssi, err, "hcitool"
    # auto: btmgmt first, hcitool fallback
    rssi, err = btmgmt_rssi(mac, adapter=adapter)
    if rssi is not None:
        return rssi, err, "btmgmt"
    rssi, err = hcitool_rssi(mac, adapter=adapter)
    return rssi, err, "hcitool"
