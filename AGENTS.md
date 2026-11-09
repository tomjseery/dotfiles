# Dotfiles

## Structure
- `core/`: personal behaviour, input, shortcuts and app preferences.
- `desktops/<desktop>/`: session setup and desktop integration.
- `themes/shared/`: appearance used across desktops or presets.
- `themes/<desktop>/<preset>/`: preset-specific visuals; `themes/current/` retains the saved KDE profile.
- `components/`: reusable integrations; `install/`: independent entry points.

## Working rules
- Give each setting one owner. Generate runtime copies from that source.
- Preserve unrelated preferences and unfinished work; change only the requested modules.
- Compose upstream projects with pinned sources and small patches; cache downloads outside Git.
- Keep credentials, sessions, caches and generated machine state outside Git.
- Use Arch-native tools and `pkexec` for root operations; never collect passwords.
- Test in isolated profiles. Do not log out, reboot or restart the live desktop for verification.

## Scoped rules
Read the relevant folder rules before editing:
- [Core](core/AGENTS.md)
- [Desktops](desktops/AGENTS.md)
- [Themes](themes/AGENTS.md)
- [Installers](install/AGENTS.md)

## Checks and agent files
- Run checks affected by the change; use `bash -n` and available ShellCheck for Bash edits.
- Keep instructions brief and local. Put usage details in the owning README; [layout](README.md).
- Edit `AGENTS.md`; each `CLAUDE.md` must be a sibling symlink to it.
