# Hyprland

## Composition
- `upstream.json` records the source revisions; `*.patch` holds local upstream changes.
- `shared/` owns controls, snapping, launchers and terminal behaviour.
- Native visual overlays belong in [the preset folders](../../themes/hyprland/AGENTS.md).

## Verification
- Use `preview.py` for nested captures and startup checks.
- Keep preview config, state, sockets and temporary images separate from the live desktop.
- Never switch live presets for screenshots or restore an old snapshot over user preferences.
