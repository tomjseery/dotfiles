# Tommy's Arch dotfiles

Managed with GNU Stow. Each top-level folder is an independent stow package —
apply only the ones you want on a given machine.

## Setting up a new machine

1. Fresh Arch install, then get git and clone this repo:

   ```sh
   sudo pacman -S --needed git
   git clone https://github.com/tomjseery/dotfiles.git ~/.dotfiles
   cd ~/.dotfiles
   ```

2. Install `yay` if this machine doesn't have an AUR helper yet:

   ```sh
   sudo pacman -S --needed base-devel
   git clone https://aur.archlinux.org/yay-bin.git /tmp/yay-bin
   (cd /tmp/yay-bin && makepkg -si)
   ```

3. Run the root-owned setup stage (official packages, `stow` itself, and
   services). This needs its own sudo prompt — never run root setup through
   an automation session:

   ```sh
   sudo bin/.local/bin/finish-arch-setup
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

6. Log out and back in — KWin needs a relogin to pick up global shortcuts,
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

The main `.bashrc` only contains a one-line loader for the managed shell
fragment, preserving the older machine-specific functions and aliases.

`restic-home` intentionally stores no password or repository URL. Configure
those through `RESTIC_REPOSITORY` and `RESTIC_PASSWORD_FILE` (or
`RESTIC_PASSWORD_COMMAND`) after choosing an external or remote destination.

`finish-arch-setup` performs the root-owned package and service stage. It is
kept separate so administrator authentication never needs to pass through an
automation session.

`packages/aur-packages.txt` is a plain list from `yay -Qqm` (AUR/foreign
packages, not a stow package itself) — see step 4 above to restore it.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
