# Shared appearance

## Modules
- Group each concern in its own folder, such as `icons/`.
- A module owns its manifest and apply helper; desktop installers call that helper.
- Merge only owned settings and preserve user colours, fonts and preset selection.
- Install external asset packs through dependencies rather than vendoring them.

## Current module
- [Application icons](icons/README.md)
