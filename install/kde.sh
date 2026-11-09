#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
if [[ ${1-} == --system && $# -eq 1 ]]; then
    exec pkexec "$repo_root/desktops/kde/system-configs/sddm/install"
fi
source "$repo_root/install/common.bash"
stow_configs "$repo_root/core/configs" kde
python3 "$repo_root/scripts/apply-settings.py" "$repo_root/core/settings" --kind kconfig "${dry_run[@]}"
