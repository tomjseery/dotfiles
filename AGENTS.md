# Repository guidance

This repository is the canonical configuration for tomjseery's Arch Linux
workstation. It is managed with GNU Stow, with one independently usable package
per top-level directory.

## Conventions

- Target Arch Linux and KDE Plasma. Prefer Arch-native tools (`pacman`, `yay`,
  systemd, and GNU Stow) over distribution-neutral abstractions.
- Keep setup scripts idempotent: rerunning one must converge on the same state
  without duplicating entries or failing because something is already present.
- Use Bash with `set -euo pipefail` for shell scripts. Run `bash -n` after
  changing a script, and use `shellcheck` when it is installed.
- Use `pkexec` for root operations so KDE presents a graphical Polkit prompt.
  Never use `sudo`, request a password in chat, or put a password in a file,
  argument, or log.
- Keep configuration declarative and store durable machine setup in this
  repository instead of relying on undocumented live-system changes.
- Keep component-specific behavior, recovery notes, and implementation history
  with that component's files or in `README.md`, not in this repository-wide
  instruction file.
- Do not add credentials, browser sessions, tokens, host inventories, or other
  machine secrets to the repository.

## Agent instruction files

`AGENTS.md` is the only editable source of repository instructions.
`CLAUDE.md` must remain a symlink to `AGENTS.md`; never replace it with a
separate file.
