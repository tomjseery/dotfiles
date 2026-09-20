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
   stow --target="$HOME" shell apps bin kde kitty konsole vscode vesktop
   ```

6. Apply the machine-wide mouse configuration as the normal desktop user:

   ```sh
   bin/.local/bin/install-mouse-config
   ```

   It removes retired global middle-button grabs, enables applications' native
   autoscroll features, and clears obsolete input-remapper autoload mappings.
   It is safe to rerun.

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
- `mouse` — shared input-remapper conflict policy used by
  `install-mouse-config`
- `app-configs` — independently installable application integrations; each app
  owns its native behavior instead of competing global mouse services
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

`packages/aur-packages.txt` lists restorable AUR packages (it is not a Stow
package itself). Application integrations can also declare required AUR
packages in their own `app-configs/<name>/aur-packages` manifest.

## Mouse and middle-click autoscroll

Linux has no desktop-wide Windows autoscroll protocol. Exact behavior requires
application context: only the application knows whether MMB landed on a link,
a tab, a message, or empty scrollable content. The canonical configuration
therefore uses native application features and deliberately has no service
that grabs the physical mouse.

`install-mouse-config` discovers app modules under `app-configs/` and restores
this state idempotently:

- `app-configs/chromium/` installs and configures `middleclick-autoscroll`. It
  enables Blink's built-in `MiddleClickAutoscroll` feature in Chrome, Chromium,
  Electron, and CEF applications and watches for newly installed apps. Chrome
  itself keeps link/tab hit-testing and draws its genuine autoscroll cursor.
- `app-configs/thunderbird/` installs Mozilla AutoConfig preferences for every
  existing and future Thunderbird profile. Gecko provides native autoscroll in
  rendered message content while retaining its own link and tab behavior.
  Its separate `styling/` module preserves usable gaps between message cards
  and a 32px right-hand gutter beside the scrollbar without changing the
  virtual list's fixed row height. Thunderbird chrome widgets such as the
  message list do not all implement the Gecko autoscroll actor; the styling
  provides a clear scroll-container target without adding another input
  service.
- input-remapper's autoload map is set to `{}` and current injections are
  stopped, removing the obsolete `disable-middle` device grabs.
- `midscroll`, `midscroll-overlay`, and `xmousepasteblock` are disabled and
  removed so exactly zero global services intercept MMB.

Apps without a native autoscroll implementation keep their ordinary MMB action.
Adding support means adding a self-contained `app-configs/<name>/` module; it
must not introduce another global middle-button owner.

After applying the configuration, fully restart affected applications. In
Chrome/webmail and other supported Blink apps, verify that MMB on a link opens a
new tab and MMB on scrollable empty content starts the native arrow cursor. In
Thunderbird, test inside a long rendered message. Ordinary left/right clicks
and native middle-click actions must remain unchanged.

Diagnostics:

```sh
middleclick-autoscroll status
middleclick-autoscroll list
systemctl --user status middleclick-autoscroll.path
systemctl is-active midscroll.service
systemctl --user is-active midscroll-overlay.service
```

Recovery is deliberately simple: `middleclick-autoscroll disable` restores the
launchers and flag files recorded in its ledger. Rerun `install-mouse-config`
to restore the repository state. Do not re-enable the old input-remapper
`disable-middle` autoload entries.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
