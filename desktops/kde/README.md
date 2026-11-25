# Pinned applications in Plasma

Icons-only Task Manager places a running window on its existing pin when
Plasma resolves the window and the pin to the same desktop entry. The saved
panel enables grouping by application and manual sorting. A launcher that
claims another application's window class can intercept the match.

From the repository root, run the checker to list desktop IDs that claim the
same identity. It reads the active XDG application directories, including
user overrides, and reports candidates for inspection.

```sh
python3 desktops/kde/launcher-identity.py
```

Compare the reported launchers with the actual app ID or resource class in
KWin's Debug Console. If a launcher incorrectly claims another app's class,
remove the incorrect hint or set the class you observed for that launcher.

```sh
python3 desktops/kde/launcher-identity.py --clear-class org.example.Alternate.desktop
python3 desktops/kde/launcher-identity.py --set-class org.example.Alternate.desktop org.example.Alternate
```

The repair changes only the selected entry's `StartupWMClass` in the user's
application directory. For a packaged launcher it creates a user override,
which takes precedence over future package updates to that desktop file.
Remove that override when the package supplies the correction. In a KDE
session the command refreshes the application cache. Keep the app pinned
through Icons-only Task Manager so the running indicator can use that pin.

A conflict report alone cannot establish which launcher should own a window.
If an app exposes no distinct identity, Plasma needs corrected metadata
from the app or an explicit mapping from the user.
