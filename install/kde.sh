#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
if [[ ${1-} == --system && $# -eq 1 ]]; then
    exec pkexec "$repo_root/desktops/kde/system-configs/sddm/install"
fi
source "$repo_root/install/common.bash"
source "$repo_root/install/lib/dotfiles/configuration.bash"
python3 "$repo_root/scripts/apply-settings.py" "$repo_root/core/config" --kind kconfig --dry-run
dotfiles_config_stow "$repo_root" kde "${#dry_run[@]}"
python3 "$repo_root/scripts/apply-settings.py" "$repo_root/core/config" --kind kconfig "${dry_run[@]}"

"$repo_root/install/icons.sh" --configs-only "${dry_run[@]}"
