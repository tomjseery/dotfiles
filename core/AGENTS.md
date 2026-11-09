# Core

## Ownership
- Mouse behaviour belongs in `mouse/`; agent helpers belong in `agents/<helper>/`.
- Split mixed app files by key: behaviour in `settings/`, appearance in `../themes/`.
- Core installation must preserve the selected desktop and visual preset.

## Integration
- Keep helpers independently installable and document them beside their code.
- For keep-awake changes, read its [behaviour and checks](agents/keep-awake/README.md).
