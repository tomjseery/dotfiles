#!/usr/bin/env bash
set -euo pipefail
configs_only=false
arguments=()
for argument in "$@"; do
    if [[ $argument == --configs-only ]]; then
        configs_only=true
    else
        arguments+=("$argument")
    fi
done
set -- "${arguments[@]}"
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.bash"
python3 "$repo_root/scripts/apply-settings.py" "$repo_root/core/settings" --dry-run
stow_configs "$repo_root/core/configs" shell apps bin kitty vscode vesktop agent-awake kde
apply_settings "$repo_root/core/settings"
loader='source "$HOME/.config/shell/interactive.bash"'
if ! grep -Fq '.config/shell/interactive.bash' "$HOME/.bashrc" 2>/dev/null; then
    if (( ${#dry_run[@]} )); then
        printf 'Would add the shell loader to ~/.bashrc\n'
    else
        printf '\n%s\n' "$loader" >> "$HOME/.bashrc"
    fi
fi
if [[ $configs_only == false ]]; then
    if (( ${#dry_run[@]} )); then
        printf 'Would install/reapply core mouse behaviour (graphical administrator approval when needed).\n'
    else
        "$repo_root/install/mouse.sh"
    fi
fi
