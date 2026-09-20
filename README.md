# tomjseery's Arch Linux dotfiles

Managed primarily with GNU Stow. User-config folders are independent Stow
packages; `mouse/`, `system-configs/`, and `packages/` are installer data rather
than files to link directly into `$HOME`.

## Setting up a new machine

1. Fresh Arch install, then get git and clone this repo:

   ```sh
   pkexec pacman -S --needed git
   mkdir -p ~/projects
   git clone https://github.com/tomjseery/dotfiles.git ~/projects/dotfiles
   cd ~/projects/dotfiles
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

   It installs midscroll as the single system-wide MMB handler, then uses a
   graphical administrator prompt to install `/etc/midscroll.conf` and enable
   the service. It is safe to rerun.

7. Reboot. SDDM is configured to start Plasma Wayland, KWin picks up the
   managed shortcuts, and the new session acquires the `libvirt` group. A plain
   logout is not sufficient for the first switch because SDDM's autologin
   session choice is applied when the display manager starts.

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
- `system-configs` — root-owned declarative configuration installed by setup
  scripts; the SDDM source selects Plasma Wayland for login

The main `.bashrc` only contains a one-line loader for the managed shell
fragment, preserving the older machine-specific functions and aliases.

`restic-home` intentionally stores no password or repository URL. Configure
those through `RESTIC_REPOSITORY` and `RESTIC_PASSWORD_FILE` (or
`RESTIC_PASSWORD_COMMAND`) after choosing an external or remote destination.

`finish-arch-setup` performs the root-owned package and service stage. It is
kept separate so administrator authentication never needs to pass through an
automation session. It also installs the canonical SDDM Wayland-session choice.

`packages/aur-packages.txt` lists restorable AUR packages (it is not a stow
package itself). The locally built `midscroll` package is intentionally absent;
`install-mouse-config` builds the pinned release itself in step 6.

## Mouse and middle-click autoscroll

`mouse/midscroll.conf` is the source of truth for `/etc/midscroll.conf`.
`install-mouse-config` is safe to rerun and restores one deliberately simple
Wayland design:

- midscroll is the single MMB owner in browsers, Electron apps, Thunderbird,
  terminals, and ordinary desktop applications;
- holding MMB and moving beyond the dead zone starts Windows-style autoscroll,
  while a quick middle click is replayed to the application so links still
  open in new tabs, terminal paste still works, and application actions are
  preserved;
- the Wayland session helper draws midscroll's official anchor badge and ghost
  cursor during an autoscroll drag;
- only applications that intentionally use native middle-drag are blacklisted
  (`freecad`, `orcaslicer`, and `minecraft`);
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
- `midscroll-overlay.service` starts with Plasma Wayland and draws the official
  overlay; no application launchers, browser flags, Thunderbird chrome, or
  synthetic X11 indicator are installed.

The installer also removes those retired integrations if they exist from an
older checkout: `middleclick-autoscroll`, its patched launchers and watcher,
the managed Thunderbird AutoConfig/stylesheets, and `xmousepasteblock`.

After applying the configuration, test a long page in Chrome/webmail, a long
message in Thunderbird, a VS Code editor, Konsole/Kitty scrollback, and another
native KDE application:

1. A quick middle click on a link opens it in a new tab; a quick middle click
   still performs the application's normal MMB action elsewhere.
2. Holding MMB and moving beyond the dead zone starts autoscroll; moving
   farther from the anchor changes speed and direction, and releasing MMB
   stops it.
3. Normal left/right clicks still activate their targets.
4. The midscroll anchor remains fixed while its ghost cursor follows the mouse.
5. `printf '%s\n' "$XDG_SESSION_TYPE"` prints `wayland`; an X11 login still
   scrolls but cannot display midscroll's overlay.

Diagnostics:

```sh
systemctl status midscroll.service
systemctl --user status midscroll-overlay.service
journalctl -u midscroll.service -b
journalctl --user -u midscroll-overlay.service -b
pkexec midscroll --list-devices
```

Recovery is deliberately simple. Stop autoscroll temporarily with
`pkexec systemctl stop midscroll.service`; restore it by rerunning
`install-mouse-config`. To remove it, run
`pkexec systemctl disable --now midscroll.service`,
then `systemctl --user disable --now midscroll-overlay.service`.

The retained input-remapper preset files can be enabled again manually only
after midscroll is removed, but never enable the old `disable-middle` autoload
entries while midscroll is running.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
