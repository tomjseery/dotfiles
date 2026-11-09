# Optional graphical shell switcher

## Authorised outcome

Add the linked upstream switcher as an optional composed dotfiles component:
pin the repository/version, keep downloaded source outside Git, supply an
independent installer, launcher and shortcut, and install/verify it locally.
Persona remains a local trial outside Git. No core/theme reapplication, desktop
session switching, logout, unrelated process termination or publication.

Checkout: `/home/tommy/projects/dotfiles`, `Feature/ShellSwitcher`, based on
local `Fix/KWinQmlDependency` at `a8c9516` because it depends on the reorganised
dotfiles layout. No PR. One bounded component slice, expected under 500 new
substantive lines plus tests/docs. No repository workflow runtime.

## Design and evidence

Investigation lane L3: upstream compatibility/scope uncertain. Implementation
and verification lane L4: bounded integration with process-isolation checks.
No session/model switch or delegated writer is claimed.

Selected upstream: `https://github.com/MannuVilasara/qswitch`, commit
`806b50900daee5a6c59084aca49c7c7f52c460cf`.
User explicitly requires reusing the existing application rather than a custom
switcher. Qswitch supplies its complete GUI and switching implementation, already
supports Lua and accepts a user config. Keep integration to a source pin,
installer, wrapper/shortcut and a small compatibility patch. The patch limits
stopping to registered profiles, supports symlinked configs and current
Quickshell keyboard-focus API, and verifies the GUI PID before toggling it.
Do not run its theme-downloading setup or config-repair commands.

Keep its mutable JSON config outside Git, initially empty. The existing Persona
trial may be registered there without committing Persona configuration. Build
and install into the user prefix. No custom GUI or replacement switch engine.
Rofi was installed while evaluating the earlier candidate; Qswitch uses its own
Quickshell GUI and does not require Rofi.

## Acceptance

- Optional component installs independently and repeatedly, with a true dry run.
- Source pin and integration are tracked; no third-party source is vendored.
- Working GUI launcher and separate optional Lua shortcut.
- Core and KDE configuration are unchanged by installation and shell switching.
- Tests prove registry validation, targeted stop/restart, and installer isolation.
- Nested Hyprland verifies real menu and Persona trial start/stop without logout.
- Changes committed locally; no Persona preset/assets added to dotfiles.

## Completed evidence

- Existing Qswitch application built from its pinned source archive into the
  user data directory. Its original GUI is used. No custom switch engine was
  implemented. Reinstallation reused the same binary and preserved local config.
- Added optional `install/qswitch.sh`, source manifest, small patch, desktop
  launcher, scoped wrapper and optional Win+Ctrl+Shift+Tab binding.
- Registered the existing Persona trial only in the user's external JSON and
  environment file; no Persona preset, configuration or assets are tracked.
- Installer dry run, shell syntax, desktop-entry validation and whitespace
  checks pass. Shellcheck is unavailable.
- Upstream Go tests pass: registered-profile stops exclude unrelated processes;
  launch resolves profile paths; external symlink configs are recognised.
- All five repository Python tests pass. New installer cases cover cached
  installation, idempotence, registration/state preservation, existing GUI
  refusal and blocking upstream setup/autofix even after an option prefix.
- Isolated nested Hyprland test displayed the real Qswitch GUI with two test
  choices, switched to the second, preserved an unregistered shell and GUI,
  preserved a personal settings sentinel, toggled the GUI closed, and proved
  that a stale GUI PID does not terminate an unrelated process.
- Real GUI screenshot and logs:
  `~/.local/state/dotfiles/qswitch/menu.png`, `gui.log`, `smoke.log`.
- Actual local registry reports the Persona trial installed. Main Hyprland
  config with the optional binding passes `--verify-config`.
- Local delivery is this commit on `Feature/ShellSwitcher`; no push requested.
- Parent reviewed the patch and installer boundaries. The native reviewer was
  previously unavailable because its app-server profile is read-only; no
  independent review is claimed. No source publication authorised or attempted.

## Next Steps

Implementation complete. User opens **Quickshell Switcher** or presses
**Win+Ctrl+Shift+Tab** inside Hyprland. Additional native Quickshell
interfaces can be registered later. Persona remains a trial until adopted.
