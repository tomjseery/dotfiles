#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
case ${1-} in
    core) manifest="$repo_root/core/packages/aur-packages.txt" ;;
    theme) manifest="$repo_root/themes/current/aur-packages.txt" ;;
    *) printf 'Usage: %s {core|theme} [--dry-run]\n' "$0" >&2; exit 2 ;;
esac
if (( $# > 2 )) || [[ ${2-} != '' && ${2-} != --dry-run ]]; then
    printf 'Only --dry-run is accepted after the module name.\n' >&2
    exit 2
fi
mapfile -t packages < <(sed '/^[[:space:]]*#/d; /^[[:space:]]*$/d' "$manifest")
if [[ ${2-} == --dry-run ]]; then
    printf '%s\n' "${packages[@]}"
else
    exec yay --sudo pkexec -S --needed -- "${packages[@]}"
fi
