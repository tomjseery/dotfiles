#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
if [[ $EUID -eq 0 ]]; then
    printf 'Run as your desktop user.\n' >&2
    exit 2
fi
if [[ ${1-} != --dry-run ]]; then
    for required in git patch python3 uv qs Hyprland kitty matugen jq fc-cache; do
        command -v "$required" >/dev/null || { printf 'Missing dependency: %s (see desktops/hyprland/README.md)\n' "$required" >&2; exit 1; }
    done
fi
exec python3 "$repo_root/desktops/hyprland/prepare.py" "$@"
