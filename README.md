# tomjseery's Arch Linux dotfiles

Managed primarily with GNU Stow. User-config folders are independent Stow
packages; `mouse/`, `app-configs/`, `system-configs/`, and `packages/` are
installer data rather than files to link directly into `$HOME`.

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
   stow --target="$HOME" shell apps bin kde kitty konsole vscode vesktop agent-awake
   systemctl --user enable --now agent-awake.service
   ```

6. Apply the machine-wide mouse configuration as the normal desktop user:

   ```sh
   bin/.local/bin/install-mouse-config
   ```

   It enables native autoscroll where an application supports it and installs
   one app-aware fallback for everything else. It also clears obsolete
   input-remapper autoload mappings. It is safe to rerun.

7. Reboot. SDDM itself and the desktop session both run on Wayland, KWin picks
   up the managed shortcuts, and the new session acquires the `libvirt` group.
   The Plasma X11 session is intentionally uninstalled, so it cannot be
   selected accidentally. `xorg-xwayland` remains as the compatibility layer
   required by legacy applications inside Plasma Wayland.

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
- `mouse` — the app-routing fallback and shared input-remapper conflict policy
  used by `install-mouse-config`
- `agent-awake` — a user service that blocks KDE's idle suspend only while a
  Claude or Codex agent is working (a transcript written in the last 10
  minutes, or an agent child process using CPU). Agents idle at their prompt
  don't block sleep. Check it with `systemd-inhibit --list` or
  `journalctl --user -u agent-awake`.
- `app-configs` — independently installable application integrations
- `system-configs` — root-owned declarative configuration installed by setup
  scripts; the SDDM source runs the greeter and Plasma session on Wayland

The main `.bashrc` only contains a one-line loader for the managed shell
fragment, preserving the older machine-specific functions and aliases.

`restic-home` intentionally stores no password or repository URL. Configure
those through `RESTIC_REPOSITORY` and `RESTIC_PASSWORD_FILE` (or
`RESTIC_PASSWORD_COMMAND`) after choosing an external or remote destination.

`finish-arch-setup` performs the root-owned package and service stage. It is
kept separate so administrator authentication never needs to pass through an
automation session. It also installs the canonical SDDM Wayland-session choice
and the Chrome enterprise policy below.

`system-configs/sddm/install` also patches `/etc/pam.d/sddm` so KWallet
auto-unlocks at login instead of prompting separately: Plasma 6 renamed the
wallet daemon to `ksecretd`, but `pam_kwallet5`'s default `auto_start` target
still points at the old `kwalletd5` binary, which no longer exists on this
system, so the patch adds `kwalletd=/usr/bin/ksecretd` explicitly. The wallet
password must also match the login password for this to actually unlock it
(set that once in KWallet's own settings; it isn't something a dotfile can
carry, per the credentials exclusion below).

`system-configs/chrome-policy` installs a machine-wide Chrome enterprise
policy (`QuicAllowed: false`) disabling QUIC/HTTP-3. QUIC runs over UDP, and
the Mullvad WireGuard tunnel this machine routes through drops/fragments QUIC
badly enough that Chrome hangs indefinitely retrying it (most visibly on
YouTube, whose video CDN opens a fresh QUIC connection per edge server) rather
than falling back to TCP promptly. Disabling it machine-wide costs a small
amount of latency on QUIC-capable sites in exchange for not hanging.

`app-configs/chromium/install-user` also writes `--password-store=basic` to
`~/.config/chrome-flags.conf`, so Chrome manages its own credential storage
instead of depending on the desktop keyring (KWallet) — a locked or
misconfigured wallet must never be able to hang the browser.

`packages/aur-packages.txt` lists restorable AUR packages (it is not a Stow
package itself). Application integrations can also declare required AUR
packages in their own `app-configs/<name>/aur-packages` manifest.

## Mouse and middle-click autoscroll

The installer in step 6 routes middle clicks by the application under the
pointer. Chrome and other supported Chromium/Electron apps keep their native
autoscroll and link-click behavior. Thunderbird, terminals, and other apps use
midscroll, with a directional cursor supplied by KWin on Plasma Wayland.

Application integrations live in `app-configs/`. When adding a native-capable
app, declare its window class in that module's `midscroll-pass-through` file;
midscroll uses window classes, while `middleclick-autoscroll` discovers desktop
apps by a different identifier. Apps without a declaration use the fallback.

`install-mouse-config` is safe to rerun. It also removes conflicting old
middle-button mappings, and installs a pacman hook to rebuild the KWin cursor
effect after KWin updates. Effect updates take effect at the next Plasma login;
the installer never unloads the effect from a running session. Restart affected
applications after applying their native-autoscroll settings.

If the cursor effect misbehaves, run
`mouse/kwin-scroll-cursor/install --disable` and log out and back in. Scrolling
will continue with midscroll's fallback indicator. After repair, re-enable
`midscrollcursorEnabled` in the managed `kde/.config/kwinrc` and log in again.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
