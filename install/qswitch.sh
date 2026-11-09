#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.bash"
component="$repo_root/components/qswitch"
mapfile -t upstream < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["repository"]); print(d["commit"])' "$component/upstream.json")
repository=${upstream[0]}
revision=${upstream[1]}
cache="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/qswitch"
root="${XDG_DATA_HOME:-$HOME/.local/share}/dotfiles/qswitch"
patch_hash=$(sha256sum "$component/compat.patch")
version="$revision-${patch_hash:0:12}"
stow --dir="$component/configs" --target="$HOME" --no-folding --simulate files
if (( ${#dry_run[@]} )); then
    printf 'Would fetch %s at %s, apply the tracked patch, test/build and install into %s.\n' "$repository" "$revision" "$root"
    printf 'Would link the GUI/shortcut and initialise an empty config only if absent.\n'
    exit 0
fi
for required in git go patch qs; do
    command -v "$required" >/dev/null || { printf 'Missing dependency: %s\n' "$required" >&2; exit 1; }
done
if [[ ! -d $cache/.git ]]; then
    git clone --no-checkout "$repository" "$cache"
fi
if ! git -C "$cache" cat-file -e "$revision^{commit}" 2>/dev/null; then
    git -C "$cache" fetch --depth 1 origin "$revision"
fi
if [[ ! -x $root/$version/qswitch ]]; then
    mkdir -p "$root"
    staging=$(mktemp -d "$root/.build.XXXXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    git -C "$cache" archive "$revision" | tar -x -C "$staging"
    patch --batch --forward --directory="$staging" -p1 < "$component/compat.patch"
    cp "$component"/upstream-tests/*_test.go "$staging/utils/"
    export GOMODCACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/go-modules"
    export GOCACHE="${XDG_CACHE_HOME:-$HOME/.cache}/dotfiles/go-build"
    export GOTOOLCHAIN=local
    (
        cd "$staging"
        go test -mod=readonly ./utils
        go build -mod=readonly -buildvcs=false -trimpath -o qswitch .
    )
    mv "$staging" "$root/$version"
    trap - EXIT
fi
if [[ -e $root/current && ! -L $root/current ]]; then
    printf 'Refusing to replace unrelated directory: %s/current\n' "$root" >&2
    exit 1
fi
ln -sfn "$version" "$root/current"
shell_dir="$HOME/.config/quickshell"
mkdir -p "$shell_dir"
if [[ -e $shell_dir/qswitch || -L $shell_dir/qswitch ]]; then
    if [[ ! -L $shell_dir/qswitch ]] || [[ $(readlink "$shell_dir/qswitch") != "$root/current/quickshell" ]]; then
        printf 'Refusing to overwrite existing Quickshell config: %s/qswitch\n' "$shell_dir" >&2
        exit 1
    fi
else
    ln -s "$root/current/quickshell" "$shell_dir/qswitch"
fi
stow_configs "$component/configs" files
mkdir -p "$HOME/.config/qswitch"
if [[ ! -e $HOME/.config/qswitch/config.json && ! -L $HOME/.config/qswitch/config.json ]]; then
    cp "$component/default-config.json" "$HOME/.config/qswitch/config.json"
fi
if [[ ! -e $HOME/.switch_state && ! -L $HOME/.switch_state ]]; then
    touch "$HOME/.switch_state"
fi
printf 'Qswitch installed. Add existing shells in ~/.config/qswitch/config.json.\n'
printf 'Load ~/.config/hypr/qswitch.lua for the optional shortcut.\n'
