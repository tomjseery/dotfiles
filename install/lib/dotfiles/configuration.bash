# shellcheck shell=bash
# Globs remain local to this subshell; arguments are repository, scope and dry-run.
dotfiles_config_stow() (
  shopt -s globstar nullglob dotglob
  local repository_root=$1 scope=$2 simulate=$3 entry legacy source relative target resolved index
  local -a packages=() migration_sources=() migration_targets=() migration_origins=() ignored=()

  while IFS=$'\t' read -r entry legacy; do
    if [[ $scope == kde && $entry != core/config/kde/files ]]; then
      continue
    fi
    [[ -d $repository_root/$entry ]] || return 1
    packages+=("$entry")
    ignored=()
    for source in "$repository_root/$entry"/**; do
      [[ -f $source ]] || continue
      relative=${source#"$repository_root/$entry/"}
      target="$HOME/$relative"
      if [[ -L $target ]]; then
        resolved=$(readlink -m -- "$target") || return
        if [[ $resolved == "$repository_root/$legacy/$relative" ]]; then
          migration_sources+=("$source")
          migration_targets+=("$target")
          migration_origins+=("$resolved")
          ignored+=("--ignore=^${relative//./\\.}$")
        fi
      fi
    done
    # Check every package before relocating any link. Ignore only exact legacy
    # links already identified above; Stow checks all other paths normally.
    command stow --dir="$repository_root/$entry/.." --target="$HOME" \
      --no-folding --simulate "${ignored[@]}" "${entry##*/}" || return
  done < "$repository_root/core/config/stow.tsv"

  for index in "${!migration_targets[@]}"; do
    target=${migration_targets[index]}
    source=${migration_sources[index]}
    if (( simulate )); then
      printf 'Would relocate managed link: %s\n' "$target"
    else
      if [[ ! -L $target || $(readlink -m -- "$target") != "${migration_origins[index]}" ]]; then
        printf 'Managed link changed during installation: %s\n' "$target" >&2
        return 1
      fi
      relative=$(realpath --relative-to="$(dirname -- "$target")" "$source") || return
      ln -sfn -- "$relative" "$target" || return
    fi
  done
  if (( simulate == 0 )); then
    for entry in "${packages[@]}"; do
      command stow --dir="$repository_root/$entry/.." --target="$HOME" \
        --no-folding "${entry##*/}" || return
    done
  fi
)
