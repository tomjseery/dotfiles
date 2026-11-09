# Astronaut login theme

Uses [SDDM Astronaut](https://github.com/Keyitdev/sddm-astronaut-theme), pinned in
`upstream.json`, with its Japanese Aesthetic preset. Only the source pin, small
configuration overrides and installers are stored here. Theme assets stay in
the cache and system theme directory. The desktop selector is labelled
**Desktop**, with readable Noto Sans text.

From the repository root:

```sh
./install/login.sh --dry-run
./install/login.sh --preview
./install/login.sh
```

Default: show this same login screen after boot and logout, remembering the
last desktop and user. Preview is SDDM test mode: it does not log you in and
needs no password. Installation opens the graphical administrator prompt and
does not restart SDDM, log out or reboot.

Options:

```sh
./install/login.sh --autologin    # sign the caller into the last-used desktop at boot
./install/login.sh --login-screen # restore the normal startup login chooser
./install/login.sh --restore      # return to previous SDDM settings
```

Automatic login bypasses the startup login screen; logout still shows it.
The installer installs one versioned theme and its fonts, then writes
`/etc/sddm.conf.d/zz-dotfiles-login.conf`. This sorts after the workstation's
existing `theme.conf` and `autologin.conf`, which are preserved. Removing only
the managed override restores those previous settings. A separate
`/etc/sddm.conf` can override conf.d settings and should be checked if another
machine carries one.

Runtime packages: `sddm`, `qt6-svg`, `qt6-virtualkeyboard`,
`qt6-multimedia-ffmpeg`; preparation also uses Git and Python. Change the source
pin or `overrides.conf` to prepare a new independently named theme version.
For a different upstream preset, change `preset` in `upstream.json` first.

Plymouth's early boot animation and desktop lock screens are separate themes.
This component changes the login screen shared by KDE and Hyprland.
