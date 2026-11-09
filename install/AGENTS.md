# Installers

## Composition
- One entry point per concern; compose existing helpers instead of duplicating their logic.
- Read dependencies and choices from the owning module's manifest.
- Run user-configuration stages as the desktop user.

## Behaviour
- Use Bash with `set -euo pipefail`; make repeat runs idempotent.
- `--dry-run` must not change files, install packages or start services.
- `--configs-only` must omit package and service changes.
- Validate inputs before writes. Merge owned keys and refuse unrelated file conflicts.
