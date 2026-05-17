"""Enumerate and resolve BlueZ Bluetooth adapters."""
from __future__ import annotations

import dataclasses
import logging
import pathlib

from PyQt6.QtDBus import QDBusConnection, QDBusMessage

from bluelock.bluetooth._types import normalize_mac

log = logging.getLogger(__name__)

_HCI_VERSIONS: dict[int, str] = {
    6: "4.0", 7: "4.1", 8: "4.2", 9: "5.0",
    10: "5.1", 11: "5.2", 12: "5.3", 13: "5.4",
}

_SYS_BT = pathlib.Path("/sys/class/bluetooth")

_BLUEZ_SVC = "org.bluez"
_BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
_DBUS_OBJMGR_IFACE = "org.freedesktop.DBus.ObjectManager"
_ZERO_ADDRESS = "00:00:00:00:00:00"


@dataclasses.dataclass(frozen=True)
class AdapterInfo:
    """A BlueZ Bluetooth adapter.

    ``address`` is the BD_ADDR — stable across reboots and USB replug, used as
    the configuration key. ``path`` is the current ``/org/bluez/hciN`` and
    may change if the adapter is unplugged and reinserted.
    """

    address: str          # upper-case colon-separated; "" if BlueZ reported a missing/zero address
    path: str             # /org/bluez/hciN
    alias: str = ""       # human-readable, user-editable; not unique
    powered: bool = False

    @property
    def hci_name(self) -> str:
        """Return the trailing ``hciN`` segment of the D-Bus path."""
        return self.path.rsplit("/", 1)[-1] if self.path else ""


def _parse_adapters(objects: dict) -> list[AdapterInfo]:
    """Build the adapter list from a ``GetManagedObjects`` reply dict.

    Pure function — split out so tests can drive it with a synthetic payload.
    Adapters with a zero/missing BD address are kept (so the user can see and
    fix them) but their ``address`` field is empty and they will not match any
    configured selection.
    """
    adapters: list[AdapterInfo] = []
    for path, interfaces in objects.items():
        if _BLUEZ_ADAPTER_IFACE not in interfaces:
            continue
        props = interfaces[_BLUEZ_ADAPTER_IFACE]
        raw_addr = str(props.get("Address", ""))
        address = normalize_mac(raw_addr)
        if raw_addr and (raw_addr == _ZERO_ADDRESS or not address):
            log.warning("Adapter %s has unusable BD address %r", path, raw_addr)
            address = ""
        adapters.append(AdapterInfo(
            address=address,
            path=str(path),
            alias=str(props.get("Alias", "")),
            powered=bool(props.get("Powered", False)),
        ))
    adapters.sort(key=lambda a: a.path)
    return adapters


def list_adapters(bus: QDBusConnection | None = None) -> list[AdapterInfo]:
    """Return all adapters currently known to BlueZ.

    Returns an empty list if BlueZ is unreachable; callers should treat that
    as "no Bluetooth available" rather than an exception.
    """
    if bus is None:
        bus = QDBusConnection.systemBus()
    if not bus.isConnected():
        log.warning("D-Bus system bus not connected; cannot list adapters")
        return []
    msg = QDBusMessage.createMethodCall(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "GetManagedObjects")
    reply = bus.call(msg)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        err = reply.errorMessage()
        if "org.freedesktop.DBus.Error.ServiceUnknown" in err or "NoReply" in err:
            log.warning("BlueZ is not running (GetManagedObjects: %s)", err)
        else:
            log.warning("GetManagedObjects failed: %s", err)
        return []
    args = reply.arguments()
    objects = args[0] if args else {}
    return _parse_adapters(objects)


def resolve_addresses(
    addresses: list[str], adapters: list[AdapterInfo] | None = None
) -> tuple[list[AdapterInfo], list[str]]:
    """Return ``(resolved, missing)`` for *addresses* (BD_ADDRs), preserving the request order.

    *resolved* contains the matching ``AdapterInfo`` objects; *missing* contains the
    normalised MAC strings for addresses that were valid but not currently present.
    Invalid MAC strings are logged and excluded from both lists.

    Empty *addresses* means "use all available adapters"; *missing* is always ``[]``
    in that case.

    *adapters* may be passed for testing; otherwise ``list_adapters()`` is called.
    """
    if adapters is None:
        adapters = list_adapters()
    if not addresses:
        return list(adapters), []

    by_addr = {a.address: a for a in adapters if a.address}
    resolved: list[AdapterInfo] = []
    missing: list[str] = []
    for raw in addresses:
        addr = normalize_mac(raw)
        if not addr:
            log.warning("Ignoring invalid adapter address: %r", raw)
            continue
        info = by_addr.get(addr)
        if info is None:
            log.warning("Configured adapter %s not currently present; skipping", addr)
            missing.append(addr)
            continue
        resolved.append(info)
    return resolved, missing


def hci_version(hci_name: str) -> str | None:
    """Return the Bluetooth version string for *hci_name* (e.g. ``"5.3"``), or ``None``.

    Reads ``/sys/class/bluetooth/<hci_name>/hci_version`` without spawning a
    subprocess.  Returns ``None`` if the sysfs file is missing or the byte value
    is not in the known table.
    """
    try:
        raw = (_SYS_BT / hci_name / "hci_version").read_text().strip()
        return _HCI_VERSIONS.get(int(raw))
    except (OSError, ValueError):
        return None
