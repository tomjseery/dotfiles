# Qswitch component

This installs [Qswitch](https://github.com/MannuVilasara/qswitch), the existing
Quickshell graphical chooser. It switches interfaces **inside Hyprland**.
The login screen selects KDE or Hyprland.

```sh
./install/qswitch.sh --dry-run
./install/qswitch.sh
```

Dependencies: Git, Go (at least the version in upstream go.mod), patch, GNU
Stow, Python and Quickshell. KDialog displays the explanatory message when the
panel is launched outside Hyprland. The graphical application itself uses
Quickshell; Rofi and AGS are not required.

`upstream.json` owns the source/version pin. Source downloads go to the user
cache; the patched application and its original QML GUI go to
`~/.local/share/dotfiles/qswitch/`. No third-party source is vendored here.
The build uses the archived revision and its go.sum, without borrowing VCS
metadata from the surrounding checkout. `compat.patch` contains the small
local integration fixes: stop registered configs by path, recognise external
symlinks, launch paths correctly, validate the panel PID before terminating it,
and use the current Quickshell keyboard-focus enum.

The installer links a desktop application and `~/.config/hypr/qswitch.lua`.
Load that optional Lua file from your Hyprland config to enable
**Win+Ctrl+Shift+Tab**, or launch **Quickshell Switcher** from the apps menu.
The installer does not edit your existing Hyprland config, core or KDE settings.

## Register an existing interface

Qswitch owns its mutable config at `~/.config/qswitch/config.json`; the installer
creates an empty default only when absent. Register native Quickshell configs
already present under `~/.config/quickshell/`, for example:

```json
{
  "flavours": ["my-shell"],
  "keybinds": {"my-shell": "default"},
  "unbinds": false,
  "panel_keybind": "SUPER + CTRL + SHIFT + Tab"
}
```

A symlink to an external interface directory containing `shell.qml` also works.
The selected name is remembered in upstream's `~/.switch_state`. For autostart,
run `qswitch apply --current` from your session startup after a selection exists.

Keep `unbinds` false and keybinds `default` to preserve your controls. Upstream
writes an optional binding fragment into its own cache, but this integration
does not source it or reapply core configuration. Service-managed interfaces
such as DMS/Whisker need their own lifecycle integration; this component's
process-isolation patch covers native Quickshell configs.

If an interface needs extra environment variables, put those in
`~/.config/qswitch/environment.bash`. The wrapper loads that local file only
for Qswitch and its child shells. Theme-specific registrations, environment,
assets and presets are not committed by this component. Persona remains a
separate local trial until explicitly adopted.

The upstream setup/autofix commands are blocked by the wrapper because they
download example themes or edit broader configuration. The normal upstream GUI,
selection and switching implementation remain in use.

## Updating and checks

Change the pinned revision deliberately, reconcile the small patch, then rerun
the installer. It builds and tests in a fresh staging directory before changing
the active version. The included upstream tests verify scoped stops, normal
launches, external symlinks and preservation of unrelated configuration.
Installed binaries are reused for an unchanged source/patch version.
