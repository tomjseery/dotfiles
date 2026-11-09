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

# Validate both managed paths before migrating anything. Unrelated files stay put.
legacy="$repo_root/core/configs/agent-awake"
module="$repo_root/core/agents/keep-awake"
paths=(.local/bin/agent-awake .config/systemd/user/agent-awake.service .local/lib/agent-keep-awake/activity.py)
migrations=()
for path in "${paths[@]}"; do
    target="$HOME/$path"
    if [[ -e $target || -L $target ]]; then
        if [[ ! -L $target ]]; then
            printf 'Refusing to overwrite unmanaged file: %s\n' "$target" >&2
            exit 1
        fi
        link=$(readlink "$target")
        if [[ $link == /* ]]; then
            resolved=$(readlink -m "$link")
        else
            resolved=$(readlink -m "$(dirname "$target")/$link")
        fi
        case $resolved in
            "$legacy/$path") migrations+=("$path") ;;
            "$module/$path") ;;
            *) printf 'Refusing to overwrite unmanaged link: %s\n' "$target" >&2; exit 1 ;;
        esac
    fi
done
for path in "${migrations[@]}"; do
    if (( ${#dry_run[@]} )); then
        printf 'Would migrate %s to core/agents/keep-awake\n' "$HOME/$path"
    else
        relative=$(realpath --relative-to="$(dirname "$HOME/$path")" "$module/$path")
        ln -sfn -- "$relative" "$HOME/$path"
    fi
done
if (( ${#dry_run[@]} && ${#migrations[@]} )); then
    # Stow cannot simulate through dangling legacy links. Both paths were checked.
    printf 'Would stow core/agents/keep-awake after migrating owned links.\n'
else
    stow_configs "$repo_root/core/agents" keep-awake
fi
if [[ $configs_only == false ]]; then
    if (( ${#dry_run[@]} )); then
        printf 'Would reload, enable and restart agent-awake.service for this user.\n'
    else
        systemctl --user daemon-reload
        systemctl --user enable agent-awake.service
        systemctl --user restart agent-awake.service
    fi
fi
