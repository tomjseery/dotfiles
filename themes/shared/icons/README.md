# Shared application icons

KDE and Hyprland use **Papirus-Dark** for application icons. Blue and Charcoal
keep the same icon set when their colours, wallpapers or transparency change.

- `theme.json` owns the theme name and Arch package.
- `apply.py` merges only icon settings into Qt/KDE, GTK and an existing scoped
  Hyprland shell configuration. It preserves colours, fonts, input settings,
  selected preset and app pins.
- `install/icons.sh` installs the package if needed and applies the choice.

```sh
./install/icons.sh --dry-run
./install/icons.sh
```

Use `--configs-only` to omit package installation. KDE/theme configuration
installers reuse that mode; Hyprland's package stage reads this manifest and its
configuration stage applies it. Changing `theme.json` and rerunning the installer
updates the saved default. KDE's live Icons setting is also read by the Hyprland
launcher, so a later selection in KDE is used when the shell next starts.

Icon artwork is installed by `papirus-icon-theme` under `/usr/share/icons/`.
The repository stores the choice and dependency, rather than a copied icon pack.
App-provided icons remain available as fallbacks for logos absent from the theme.
Reopen applications or start the next desktop session to refresh cached icons;
the installer does not log out or restart either desktop.
