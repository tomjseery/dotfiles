# Firefox launcher identity

Core installation corrects the legacy `firefox-no-vpn.desktop` launcher if it
claims the native Firefox window class. This keeps Plasma from associating the
normal browser window with the Flatpak launcher. The installer leaves a missing
launcher and its other settings untouched. When run in KDE, the installer refreshes the application database after a change.
