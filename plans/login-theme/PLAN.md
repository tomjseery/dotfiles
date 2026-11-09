# Consistent login theme

## Scope and authority

User selected SDDM Astronaut after asking for a better login screen shared by
boot and logout. Use the Japanese Aesthetic preset as the stated starting
choice. Reuse upstream theme, keep assets outside Git and supply a separate
installer. User wants options with a sensible default: show the login chooser,
remember the last desktop/user, and support optional automatic login. Preserve
the running session; no SDDM restart/logout/reboot. Persona remains outside Git.

Repository: `/home/tommy/projects/dotfiles`, branch `Feature/LoginTheme`, based
on `Feature/ShellSwitcher` at `79592d6` because the installer uses the reorganised
layout. Existing KDE shortcuts, panel-state edits and old-path `kde/` files are
live-session changes, preserved and excluded from this delivery slice.

## Implementation

- Pin `Keyitdev/sddm-astronaut-theme` at
  `abb3163c724935af888ba5ea9ac0c4f22afd8048`.
- `themes/login/astronaut/` owns source pin, small preset overrides and root
  installation; `install/login.sh` is the user entry point.
- Default shows the login screen at boot and after logout; explicit optional
  autologin uses the caller and last selected session.
- Preserve the existing SDDM theme/config; add one managed override and an
  independently installed upstream theme. Never restart the active manager.
- Preview the actual selected theme with SDDM test mode and verify that the
  visible desktop selector lists Hyprland and Plasma before applying it.
- Boot animation (Plymouth) and desktop lock screens are separate and outside
  this selected login-theme change.

## Verification / progress

All Qt/SDDM runtime dependencies are installed. Source is cached (36 MB).
Investigation lane L3: inspect real greeter and config precedence. Implementation
and validation lane L4: bounded installer and direct GUI checks. Work stays in
this session; no model switch or external writer claimed.

## Completion evidence

Installed the selected version through `pkexec`. Effective SDDM configuration
resolves to `dotfiles-astronaut-abb3163c7249-japanese_aesthetic-483db293`, empty
Autologin User (normal startup chooser), and remember-last-user/session enabled.
The existing Wayland greeter settings are retained. The managed override is
`/etc/sddm.conf.d/zz-dotfiles-login.conf`, which sorts after the existing theme
and autologin files. Those originals remain available for `--restore`.

SDDM test mode rendered the actual pinned theme at 2560×1080. Its real session
model contained Hyprland and Plasma; the screenshot was saved only after both
were present. The visible selector reads Desktop. Noto Sans replaces the
preset's stylised font for readability. Evidence is local runtime state:
`/home/tommy/.local/state/dotfiles/login-theme/verified-preview.png`.
Installed files exactly match the tested prepared theme. SDDM remains active
with the original PID 991; no restart, logout, reboot or real login was performed.
The daemon's upstream 0.21.0 Seat.cpp reloads configuration when creating a new
display, so the override is intended for the next logout or boot.

Validation: all seven repository unit tests pass; Bash syntax checks and
`git diff --check` pass. Shellcheck is not installed. Manual installer/config
review completed; no independent reviewer result is claimed. Optional autologin
and restore paths were checked in dry-run mode, without changing the selected
default. Persona remains outside Git and unrelated live KDE files are excluded.

## Next Steps

Implementation complete. The next logout or boot will exercise the production
greeter; actual authentication and boot were intentionally not forced during
this session. Optional policies and rollback are documented in
`themes/login/astronaut/README.md`. No publication was requested.
