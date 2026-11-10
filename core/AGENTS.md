# Core

## Ownership
- Mouse behaviour belongs in `mouse/`; agent helpers belong in `agents/<helper>/`.
- App configuration belongs in `config/apps/<app>/`; shell, KDE and machine
  configuration belong in `config/shell/`, `config/kde/` and `config/system/`.
- Keep complete linked files in the owner's `files/` and merged keys in its
  `settings/`. Appearance belongs in `../themes/`; executable helpers in `commands/`.
- Core installation must preserve the selected desktop and visual preset.

## Integration
- Keep helpers independently installable and document them beside their code.
- For keep-awake changes, read its [behaviour and checks](agents/keep-awake/README.md).
