#!/usr/bin/env bash
# Shared by the explicit installation entry points.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dry_run=()
if [[ ${1-} == --dry-run ]]; then
    dry_run=(--dry-run)
    shift
fi
if (( $# )); then
    printf 'Unexpected argument: %s\n' "$1" >&2
    exit 2
fi
if [[ $EUID -eq 0 ]]; then
    printf 'Run user configuration installers as your desktop user.\n' >&2
    exit 2
fi
# Stow packages use normal ~/.config paths throughout this workstation repo.
if [[ ${XDG_CONFIG_HOME:-$HOME/.config} != "$HOME/.config" ]]; then
    printf 'This workstation layout requires XDG_CONFIG_HOME=$HOME/.config.\n' >&2
    exit 2
fi
stow_configs() {
    local directory=$1
    shift
    command stow --dir="$directory" --target="$HOME" --no-folding --simulate "$@"
    if (( ${#dry_run[@]} == 0 )); then
        command stow --dir="$directory" --target="$HOME" --no-folding "$@"
    fi
}
apply_settings() {
    python3 "$repo_root/scripts/apply-settings.py" "$1" "${dry_run[@]}"
}
