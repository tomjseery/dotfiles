# Organise dotfiles

## Outcome and authority

User authorised implementation here in this session. Keep everything in this
repository, with one `core/` home for personal behaviour (especially MMB scroll),
separate desktop/theme modules, and independent shell installers. Preserve the
current live setup and all pre-existing changes. No new desktop or Persona
installation is part of this reorganisation; do not publish without authority.

## Design

- `core/`: personal config packages, mouse integration, application behaviour,
  system policy and package lists.
- `desktops/kde/`: KDE session/system installation.
- `themes/current/`: existing appearance, assets and panel layout.
- `install/`: explicit core, mouse, system, desktop, AUR and theme entry points.
- Split settings that mix behaviour and appearance into overlays. Applying a
  theme reasserts core settings, preserving unrelated live keys.
- Keep external artwork outside Git; record required existing assets.

## Verification and completion

Snapshot current tracked files and managed links outside Git before moving them.
Preserve all managed links and file contents through migration. Check shell
syntax, installer dry runs, isolated-home install/idempotence, and behaviour
preservation when applying a theme. Review the complete diff and make local
commits; report remaining remote/publication limits honestly.

## Progress

- Existing checkout: `/home/tommy/projects/dotfiles`, main at `feb1e55`.
- Pre-existing changes: KDE shortcuts, KWin, panel state and shell fragment.
- 33 managed live symlinks found, including directory links and a systemd link.
- No repository engineering runtime. Standalone plan-execution applies.
- Remote fetch failed because github.com DNS was unavailable; local main and
  cached origin/main match. Work can proceed locally without remote mutation.
- Investigation lane L3: mixed KConfig and application config need ownership
  decisions. Implementation lane L4: migration and installers require focused
  verification. No native model-switch control exposed; no model switch claimed.
- User explicitly requested all work in this session; no new session launched.
- Snapshot: `/home/tommy/.local/state/dotfiles/backups/20261109-000846-before-layout`.
- Layout and installers implemented; mouse is under core and included by the
  main core installer, with a separate entry point for independent reapplication.
- Mixed KDE/app settings split into core and theme fragments; Kitty uses an
  included theme file. All 33 prior managed live paths still resolve.
- Applied config-only core and current appearance locally, without reinstalling
  packages, invoking root, restarting services, or changing desktop sessions.
- Three disposable-home tests pass: install/idempotence/core protection,
  refusal of existing unrelated files, and refusal of invalid JSON before writes.
- Bash syntax and Python parsing pass. Shellcheck is not installed.
- One atomic layout slice: existing assets move mechanically; settings splitting,
  link repair and installer paths must converge together. No large unrelated work.
- Original local preferences saved independently in commit `6b1d566` before the
  layout commit. Refactor is on `Refactor/DotfilesLayout`.
- Three tests also pass from a fresh `git archive` export. Removed an empty
  Vesktop Stow package from selection; its settings are supplied by overlays.
- Final local core/theme dry runs and split AUR manifest checks pass; working
  config has MMB cursor enabled and primary-selection/middle-click paste disabled.
- Native `codex review` was attempted but could not initialise its app server
  because its profile filesystem is read-only. No independent review is claimed.
  Parent inspected installer root resolution, Stow conflicts, layer ordering,
  mixed-file ownership, executable bits, live links and preserved assets.
- Root package installer now explicitly includes Python for settings merging.
- Existing CLAUDE.md symlink to AGENTS.md remains intact as the user requires.
- Local completion verified. No package/root/service operations were rerun.
  Remote publication was not requested and no push was attempted.

## Next Steps

None for the authorised local reorganisation. Publication and installing a new
desktop/theme are separate future actions.
