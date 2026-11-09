#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
mapfile -t packages < "$repo_root/desktops/hyprland/packages.txt"
if [[ ${1-} == --dry-run && $# == 1 ]]; then
    printf 'Would install Arch packages through graphical approval:\n'
    printf '  %s\n' "${packages[@]}"
    exit 0
fi
if (( $# )); then
    printf 'Usage: %s [--dry-run]\n' "$0" >&2
    exit 2
fi
exec pkexec pacman -S --needed --noconfirm "${packages[@]}"
