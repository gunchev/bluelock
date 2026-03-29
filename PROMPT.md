# BlueLock

## Prompt 1 - plan creation 2026-03-29

Prepare a plan for the following GUI python application, targeting KDE primarily. It should monitors bluetooth devices
and uses their distance/absence to lock and unlock the user session. There is an
[old project](/home/dgunchev/dev/python/bluetooth_tests/blueproximity) that was doing it, but the UI no longer works
properly and the code needs cleaning up. The app should display an animated icon in the system tray showing distance and
on right click show configuration menu, help and about. The configuration should allow selecting device, function,
display real-time signal strength/estimated distance. There must be two thresholds - level and time below/above - to
unlock and lock the desktop session. Prepare a plan, ask when there are options (like what systray icon library to use)
and write requirements and plan in markdown. The app layout should be with `src` directory, Makefile, similar
to [keyclean](/home/dgunchev/github/gunchev/keyclean).


## Prompt 2

Write the plan in `PLAN.md`.

## Prompt 3

Start implementing phase 1.

## Prompt 4

Do not use the super verbose function calls where each parameter is on new line. Keep it one-line where possible.

## Prompt 5

Please proceed with the plan.

## Prompt 6

Commit everything and make release 0.0.1, rpm revision 0.

## Prompt 7

Running the resulting app (installed the RPM) results in:

```
WARNING bluelock.tray: Icon not found: /usr/lib/python3.14/resources/icons/bluelock_close.svg
WARNING bluelock.tray: Icon not found: /usr/lib/python3.14/resources/icons/bluelock_far.svg
WARNING bluelock.tray: Icon not found: /usr/lib/python3.14/resources/icons/bluelock_gone.svg
WARNING bluelock.tray: Icon not found: /usr/lib/python3.14/resources/icons/bluelock_error.svg
WARNING bluelock.tray: Icon not found: /usr/lib/python3.14/resources/icons/bluelock_paused.svg
QSystemTrayIcon::setVisible: No Icon set
INFO bluelock.app: No device configured — opening preferences
INFO bluelock.bluetooth._bluez_dbus: Starting device scan (timeout=10000ms)
Traceback (most recent call last):
File "/usr/bin/bluelock", line 8, in <module>
sys.exit(main())
~~~~^^
File "/usr/lib/python3.14/site-packages/bluelock/app.py", line 189, in main
bluelock.start()
~~~~~~~~~~~~~~^^
File "/usr/lib/python3.14/site-packages/bluelock/app.py", line 54, in start
self._show_preferences()
~~~~~~~~~~~~~~~~~~~~~~^^
File "/usr/lib/python3.14/site-packages/bluelock/app.py", line 142, in _show_preferences
self._monitor.start_scan()
~~~~~~~~~~~~~~~~~~~~~~~~^^
File "/usr/lib/python3.14/site-packages/bluelock/bluetooth/_bluez_dbus.py", line 104, in start_scan
self._connect_object_manager_signals()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
File "/usr/lib/python3.14/site-packages/bluelock/bluetooth/_bluez_dbus.py", line 133, in _connect_object_manager_signals
self._bus.connect(_BLUEZ_SVC, "/", _DBUS_OBJMGR_IFACE, "InterfacesAdded",
~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
self._on_interfaces_added)
^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: callable must be a method of a QtCore.QObject instance decorated by QtCore.pyqtSlot
```
