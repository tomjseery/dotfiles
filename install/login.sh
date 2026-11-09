#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
component="$repo_root/themes/login/astronaut"
mode=--login-screen
preview=false
dry_run=false
restore=false
for argument in "$@"; do
    case $argument in
        --login-screen|--autologin) mode=$argument ;;
        --preview) preview=true ;;
        --dry-run) dry_run=true ;;
        --restore) restore=true ;;
        *) printf 'Usage: %s [--login-screen|--autologin] [--preview|--dry-run|--restore]\n' "$0" >&2; exit 2 ;;
    esac
done
if [[ $EUID -eq 0 ]]; then
    printf 'Run this as your desktop user; the system stage uses pkexec.\n' >&2
    exit 2
fi
if [[ $restore == true ]]; then
    if [[ $dry_run == true ]]; then
        printf 'Would restore the previous SDDM theme and login policy.\n'
    else
        exec pkexec "$component/install-system" --restore
    fi
    exit 0
fi
mapfile -t upstream < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["repository"]); print(d["commit"])' "$component/upstream.json")
cache="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/sddm-astronaut-theme"
if [[ $dry_run == true ]]; then
    printf 'Would prepare pinned SDDM Astronaut (Japanese Aesthetic), mode %s.\n' "$mode"
    printf 'Would %s. The current session is never restarted.\n' "$([[ $preview == true ]] && echo 'open a non-authenticating preview' || echo 'install the theme and one SDDM override through pkexec')"
    exit 0
fi
for package in sddm qt6-svg qt6-virtualkeyboard qt6-multimedia-ffmpeg; do
    pacman -Q "$package" >/dev/null 2>&1 || { printf 'Missing package: %s\n' "$package" >&2; exit 1; }
done
if [[ ! -d $cache/.git ]]; then
    git clone --no-checkout "${upstream[0]}" "$cache"
fi
if ! git -C "$cache" cat-file -e "${upstream[1]}^{commit}" 2>/dev/null; then
    git -C "$cache" fetch --depth 1 origin "${upstream[1]}"
fi
prepared=$(python3 "$component/prepare.py" "$cache" "$component" "${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/login-themes")
if [[ $preview == true ]]; then
    printf 'Preview only: no real login and no system changes.\n'
    exec sddm-greeter-qt6 --test-mode --theme "$prepared"
fi
exec pkexec "$component/install-system" "$prepared" "$mode"
