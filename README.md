# Tommy's Arch dotfiles

Managed with GNU Stow. Each top-level folder is an independent stow package —
apply only the ones you want on a given machine:

```sh
stow --target="$HOME" shell apps bin kde kitty konsole vscode vesktop
```

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

## Packages (not stowed)

`packages/aur-packages.txt` is a plain list from `yay -Qqm` (AUR/foreign
packages). Restore them on a new machine with:

```sh
yay -S --needed - < packages/aur-packages.txt
```

Official repo packages are still handled by `finish-arch-setup`.

## Things deliberately kept out of this repo

Anything that's an account, session, or credential rather than a setting:
browser profiles (cookies/logins), `~/.config/gh` (GitHub token), Discord/
Vesktop session data, Mullvad/Proton account state, and any crypto wallet
data. Theme and keybinding *choices* are portable; logged-in sessions and
secrets are not.
