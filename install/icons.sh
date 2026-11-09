#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
configs_only=false
preview=false
for argument in "$@"; do
    case "$argument" in
        --configs-only) configs_only=true ;;
        --dry-run) preview=true ;;
        *) printf 'Usage: %s [--configs-only] [--dry-run]\n' "$0" >&2; exit 2 ;;
    esac
done
if [[ $EUID -eq 0 ]]; then
    printf 'Run as your desktop user.\n' >&2; exit 2
fi
if [[ ${XDG_CONFIG_HOME:-$HOME/.config} != "$HOME/.config" ]]; then
    printf 'Shared desktop configuration requires XDG_CONFIG_HOME=$HOME/.config.\n' >&2; exit 2
fi
component="$repo_root/themes/shared/icons"
package=$(python3 "$component/apply.py" --package)
if ! $configs_only; then
    if $preview; then
        printf 'Would ensure Arch package %s is installed.\n' "$package"
    elif ! pacman -Q "$package" >/dev/null 2>&1; then
        pkexec pacman -S --needed --noconfirm "$package"
    fi
fi
arguments=()
if $preview; then arguments+=(--dry-run); fi
python3 "$component/apply.py" "${arguments[@]}"
