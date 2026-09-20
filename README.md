# tomjseery's Arch Linux dotfiles

Managed primarily with GNU Stow. User-config folders are independent Stow
packages; `mouse/`, `app-configs/`, and `packages/` are installer data rather
than files to link directly into `$HOME`.

## Setting up a new machine

1. Fresh Arch install, then get git and clone this repo:

   ```sh
   pkexec pacman -S --needed git
   git clone https://github.com/tomjseery/dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ```

2. Install `yay` if this machine doesn't have an AUR helper yet:

   ```sh
   pkexec pacman -S --needed base-devel
   git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin
   (cd /tmp/yay-bin && makepkg --clean --cleanbuild --noconfirm)
   pkexec pacman -U --needed --noconfirm /tmp/yay-bin/yay-bin-*.pkg.tar.zst
   ```

3. Run the root-owned setup stage (official packages, `stow` itself, and
   services). `pkexec` opens KDE's graphical administrator prompt:

   ```sh
   pkexec bin/.local/bin/finish-arch-setup
   ```

4. Restore AUR packages:

   ```sh
   yay -S --needed - < packages/aur-packages.txt
   ```

5. Stow whichever packages you want on this machine (see below for what each
   one contains — you don't have to take all of them):

   ```sh
   stow --target="$HOME" shell apps bin kde kitty konsole vscode vesktop
   ```

6. Apply the machine-wide mouse configuration as the normal desktop user:

   ```sh
   bin/.local/bin/install-mouse-config
   ```

   It installs and configures both native Chromium/Electron autoscroll and the
   midscroll fallback, then uses graphical administrator prompts to install
   `/etc/midscroll.conf` and enable the system service. It is safe to rerun.

7. Log out and back in — KWin needs a relogin to pick up global shortcuts,
   and you need to log out/in to acquire the `libvirt` group.

## Packages

- `shell` / `apps` / `bin` — shell config, autostart, fastfetch, MangoHud, yazi
- `kde` — Plasma/KWin theme and global shortcuts (kwinrc, kglobalshortcutsrc,
  kdeglobals, klassyrc, kxkbrc, panel layout, Kvantum theme selection,
  Catppuccin/custom color schemes, Aurorae window decoration themes)
- `kitty` — terminal config
- `konsole` — Konsole is a Flatpak, so its config lives under
  `~/.var/app/org.kde.konsole/config`, not `~/.config`. The SSH host list
  (`konsolesshconfig`) is intentionally excluded — it names real remote hosts.
- `vscode` — `settings.json` and `keybindings.json` only (no extensions,
  cache, or workspace storage)
- `vesktop` — Vencord theme/QuickCSS only (no session data, tokens, or
  Crashpad/session folders — those never leave the live machine)
- `mouse` — source configuration for system-wide Windows-style middle-click
  autoscroll and the input-remapper conflict policy (applied by
  `install-mouse-config`, not Stow)
- `app-configs` — application- or engine-specific source files consumed by
  installers rather than Stow; shared Chromium behavior and Thunderbird's
  Gecko-specific behavior are kept separate here

An app integration may provide an `aur-packages` manifest and executable
`install-user` and/or `install-system` hooks. `install-mouse-config` discovers
those hooks automatically, so another application can be added in its own
folder without folding its implementation into the central installer.

The main `.bashrc` only contains a one-line loader for the managed shell
fragment, preserving the older machine-specific functions and aliases.

`restic-home` intentionally stores no password or repository URL. Configure
those through `RESTIC_REPOSITORY` and `RESTIC_PASSWORD_FILE` (or
`RESTIC_PASSWORD_COMMAND`) after choosing an external or remote destination.

`finish-arch-setup` performs the root-owned package and service stage. It is
kept separate so administrator authentication never needs to pass through an
automation session.

`packages/aur-packages.txt` lists restorable AUR packages (it is not a stow
package itself). The locally built `midscroll` package is intentionally absent;
`install-mouse-config` builds the pinned release itself in step 6.

## Mouse and middle-click autoscroll

`mouse/midscroll.conf` is the source of truth for `/etc/midscroll.conf`.
`app-configs/chromium/middle-click-autoscroll.conf` controls the shared native
Chromium/Electron/CEF integration. The files under
`app-configs/thunderbird/middle-click-autoscroll/` configure Gecko's native
behavior installation-wide without storing mail profiles. This keeps shared
physical-input policy separate from app-specific integration.

`install-mouse-config` is safe to rerun and restores the complete setup,
including packages, generated launchers, application integration, service
state, input-remapper policy, and one owner for each middle click:

- `middleclick-autoscroll` enables Blink's built-in Windows-style autoscroll in
  Chrome, webmail, VS Code, Vesktop, and other Chromium/Electron/CEF apps;
- those window classes are excluded from midscroll, so the application receives
  the real middle click and draws its normal fixed circular origin marker and
  direction-changing cursor;
- Thunderbird is configured through Mozilla AutoConfig and excluded from
  midscroll, giving every existing or future mail profile Gecko's native
  autoscroll UI while disabling Linux middle-click paste inside Thunderbird;
  traditional scrollbars stay visible so scrollable panes are identifiable;
- midscroll uses click-to-toggle mode as the system-wide fallback in terminals
  and native desktop applications that do not implement autoscroll themselves;
- ordinary left and right clicks pass through unchanged while autoscroll is
  idle; as on Windows, a click made during autoscroll stops it without also
  activating whatever is under the pointer;
- input-remapper's autoload map is set to `{}` and current injections are
  stopped, so its old `disable-middle` presets do not grab either the Razer
  DeathAdder or Rainy 75 mouse interface;
- the redundant `xmousepasteblock` systemd and XDG-autostart instances are
  stopped and the package is removed, eliminating another competing MMB hook;
- the virtual `input-remapper mouse` device is explicitly ignored by
  midscroll, preventing a virtual-device grab loop;
- `midscroll-overlay.service` starts with the graphical user session so the
  application blacklist works and the fallback Wayland overlay can be drawn;
- `middleclick-autoscroll.path` watches for newly installed Chromium-based apps
  and patches their launchers automatically.

The native marker and directional cursor are application UI, not a cursor-theme
asset. Applications need to be restarted after the installer adds their native
configuration. On Plasma X11, midscroll's fallback still scrolls applications
without native support, but midscroll itself has no X11 marker; its upstream
overlay is available on Wayland. The setup deliberately does not draw a custom
lookalike icon.

After applying the configuration, test a long page in Chrome/webmail, a long
message in Thunderbird, a VS Code editor, Konsole/Kitty scrollback, and another
native KDE application:

1. A middle click starts autoscroll; moving away from the anchor changes speed
   and direction.
2. A second middle click, left click, or right click stops it.
3. Normal left/right clicks still activate their targets when autoscroll is
   inactive.
4. In Chrome/webmail, Thunderbird, and VS Code, the native circular anchor
   stays fixed and the cursor changes to directional arrows as it moves around
   the anchor.
5. In terminals and other fallback apps, scrolling works even though X11 has
   no midscroll fallback marker.

Thunderbird's native autoscroll operates in rendered message/web content. Its
message-list pane deliberately assigns middle click to opening a message, so
test the native anchor inside a long message or another scrollable page in the
right-hand content pane.

Diagnostics:

```sh
systemctl status midscroll.service
systemctl --user status midscroll-overlay.service
systemctl --user status middleclick-autoscroll.path
middleclick-autoscroll status
middleclick-autoscroll list
journalctl -u midscroll.service -b
journalctl --user -u midscroll-overlay.service -b
pkexec midscroll --list-devices
```

Recovery is deliberately simple. Stop autoscroll temporarily with
`pkexec systemctl stop midscroll.service`; restore it by rerunning
`install-mouse-config`. To remove it, run
`pkexec systemctl disable --now midscroll.service`,
`systemctl --user disable --now midscroll-overlay.service`, then
`middleclick-autoscroll disable`. Remove Thunderbird's native integration with:

```sh
pkexec rm -f \
    /usr/lib/thunderbird/defaults/pref/tomjseery-autoscroll.js \
    /usr/lib/thunderbird/tomjseery-autoscroll.cfg
```

The retained input-remapper preset files can be enabled again manually only
after midscroll is removed, but never enable the old `disable-middle` autoload
entries while midscroll is running.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
