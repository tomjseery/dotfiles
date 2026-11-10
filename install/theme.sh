#!/usr/bin/env bash
set -euo pipefail
# The saved current profile is the only installed theme module for now.
# shellcheck source-path=SCRIPTDIR
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.bash"
theme_dir="$repo_root/themes/current"
layout=plasma-org.kde.plasma.desktop-appletsrc
if [[ ${XDG_CURRENT_DESKTOP-} == *KDE* ]] && \
    ! cmp -s "$theme_dir/files/.config/$layout" "$HOME/.config/$layout"; then
    printf 'Apply panel layouts outside a running Plasma session; log out first.\n' >&2
    exit 1
fi
python3 "$repo_root/scripts/apply-settings.py" "$theme_dir/settings" --dry-run
python3 "$repo_root/scripts/apply-settings.py" "$repo_root/core/config" --dry-run
stow_configs "$theme_dir" files
apply_settings "$theme_dir/settings"
apply_settings "$repo_root/core/config"
if (( ${#dry_run[@]} == 0 )); then
    "$theme_dir/thunderbird/install.sh"
fi
printf 'Current appearance profile prepared. Reopen apps or log in again to reload it.\n'

"$repo_root/install/icons.sh" --configs-only "${dry_run[@]}"
