# BlueLock


## Prompt 1 - plan creation 2026-03-29

Prepare a plan for the following GUI python application, targeting KDE primarily. It should monitors bluetooth devices and uses their distance/absence to lock and unlock the user session. There is an 
[old project](/home/dgunchev/dev/python/bluetooth_tests/blueproximity) that was doing it, but the UI no longer works properly and the code needs cleaning up. The app should display an animated icon in the system tray showing distance and on right click show
configuration menu, help and about. The configuration should allow selecting device, function, display real-time signal strength/estimated distance. There must be two thresholds - level and time below/above - to unlock and lock the desktop session.
Prepare a plan, ask when there are options (like what systray icon library to use) and write requirements and plan in markdown. The app layout should be with `src` directory, Makefile, similar to [keyclean](/home/dgunchev/github/gunchev/keyclean).
