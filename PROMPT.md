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

## Prompt 8

After starting the application with `make run` pressing Ctrl+C is ignored, it does not exit.

## Prompt 9

At start, Ctrl+C is ignored till the configuration dialog is dismissed. Closing it and right-clicking to get it back
honors Ctrl+C.

## Prompt 10

Pressing scan does not show any available devices. I get the following logs though:

```
INFO bluelock.app: No device configured — opening preferences
INFO bluelock.bluetooth._bluez_dbus: Starting device scan (timeout=10000ms)
qt.dbus.integration: Could not connect "org.freedesktop.DBus.ObjectManager" to _on_interfaces_added(QString,PyQt_PyObject) : Type not registered with QtDBus in parameter list: PyQt_PyObject
INFO bluelock.bluetooth._bluez_dbus: Stopping device scan
qt.dbus.integration: Could not disconnect "org.freedesktop.DBus.ObjectManager" to _on_interfaces_added(QString,PyQt_PyObject) : Type not registered with QtDBus in parameter list: PyQt_PyObject
```

## Prompt 11

There is a bluetooth device "Don XQ-DQ54" with MAC address "XX:XX:XX:XX:XX:XX". Why can't I see it in the list?
The command `bt-device -l` shows it.

## Prompt 12

I can see it reliably now, but the RSSI remains -100.

## Prompt 13

The readings are strange and inconsistent. Make a command line app that accepts a MAC and displays RSSI "real-time" -
`uv run bluelock_mon 'XX:XX:XX:XX:XX:XX'`.

## Prompt 14

I get `-48 dBm` all the time. If I turn off the bluetooth on the device I get a single
`21.7s  PropsChanged    (keys: Connected)`. When I turn it back on - again `PropsChanged    (keys: Connected)`.
But the signal remains "-48 dBm".

## Prompt 15

Running `btmgmt get-conn-info XX:XX:XX:XX:XX:XX 'BR/EDR'` results in error
`Invalid command in menu mgmt: get-conn-info`. The `hcitool` does display from 0 to -18 when I move the device.

## Prompt 16

The `sudo btmgmt conn-info XX:XX:XX:XX:XX:XX 'BR/EDR'` does work, why remove it? Also, `/usr/bin/hcitool` is part
of `bluez-deprecated`, which will be removed soon.

## Prompt 17

Keep both options, `btmgmt` will require extra group or sudo.

## Prompt 18

Now `sudo uv run bluelock_mon 'XX:XX:XX:XX:XX:XX'` works. What permissions do I need to run
`btmgmt conn-info XX:XX:XX:XX:XX:XX 'BR/EDR'` without sudo?

## Prompt 19

Yes, let's go that route. There is no `bluetooth` group though, at all, in the whole system. How about the `users` group?

## Prompt 20

Nice, both report the same RSSI. Make the preferences dialog show up and hide on left button click on the icon.
Make the dialog 50% wider and two tabs: selecting the device and configuration. This will show more devices at once.
Check why the distance remains '-' all the time too. Make both durations default to 4 seconds.

## Prompt 21

Move the RSSI display to tab 2 and tab 1's device list resize vertically with the window. "Use Selected" should
move to tab 2.

## Prompt 22

Make double clicking on a device on the device table select the device and move to page 2. Move the "Use selected
device" button next to "Search" and name it "Use".

## Prompt 23

Increase the "MAC" column width by 50% to fit the whole MAC.

## Prompt 24

Make the config window 20% taller and commit the changes so far.

## Prompt 25

Update PROMPT.md for me please, with all prompts. Mask the MAC addresses with 'XX:XX:XX:XX:XX:XX'.

## Prompt 26

If the device is configured make the config window open the settings tab instead of the device tab.

## Prompt 27

The red icon does not persist - shows up only when opening the configuration dialog. What do the different color
icons show?

## Prompt 28

Use the `bluelock_far.svg` to show when the device is far and lock is pending/active. Use `bluelock_gone.svg` when
the device is absent only. Document these in the README.md file.

## Prompt 29

The app does not seem to lock/unlock. The icon is most of the time gray, sometimes blinks red.

## Prompt 30

Locking works, unlocking however prints the log message but nothing happens. I have to unlock by hand.

## Prompt 31

`ERROR bluelock.app: Unlock failed: Cannot find login1 session: Invalid arguments 'i' to call
org.freedesktop.login1.Manager.GetSessionByPID(), expecting 'u'.`

## Prompt 32

Seems to work. Please update the PROMPT.md and commit the changes.

## Prompt 33

In the options, "Settings" tab, add a checkbox to auto-start on login. Make the dialog 15% taller to fit everything.

## Prompt 34

Make release 0.1.0, update PROMPT.md, commit.

## Prompt 35

`make rpm` ends with `install: cannot stat '/home/dgunchev/rpmbuild/SOURCES/bluelock-sudoers': No such file or directory`.

## Prompt 36

When the monitored device is near how can we prevent KDE from locking the screen?

## Prompt 37

Update the PROMPT.md and commit. Tag new minor release.

## Prompt 38

Looks amazing. Please change the configuration dialog's "Settings" tab to be dynamically created when a device is
selected, the name of the tab to be the MAC address. The goal is to allow for up to 4 devices to be configured at
the same time. If there are devices configured, do not trigger scan when the configuration is opened, just focus the
latest tab. Add a button to forget a device.

## Prompt 39

The RSSI for all devices seems the same.

## Prompt 40

OK, limit to single device. Lock the "Device" tab till the device is forgotten. At this point lock the "Settings"
till a device is selected.

## Prompt 41

Move the advanced settings to the device tab. No point starting on login without configuration.

## Prompt 42

Name the first tab "Devices" and the second "Settings".

## Prompt 43

Update PROMPT.md.

## Prompt 44 (Junie)

Examine the project. Look for errors and optimization/cleanup opportunities.

## Prompt 45

Look like a good improvement list. Please proceed with these one by one and commit after each step.

## Prompt 46

Change the configuration logic to support only one device. What is left to improve?

## Prompt 47

I got this error:
```
WARNING bluelock.app: Bluetooth monitor error: Bluetooth discovery error: Operation already in progress
INFO bluelock.bluetooth._bluez_dbus: Stopping device scan
Traceback (most recent call last):
File "/home/dgunchev/github/gunchev/bluelock/src/bluelock/config_dialog.py", line 371, in _on_accept
_set_autostart(self._device_tab.autostart_enabled() if self._device_tab else False)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^
TypeError: 'bool' object is not callable
make: *** [Makefile:112: run] Error 134
```

## Prompt 48

Update PROMPT.md and commit the changes.
