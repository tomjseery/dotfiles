#!/usr/bin/env bash
set -euo pipefail

integration_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
source_stylesheet="$integration_dir/styling/userChrome.css"
profiles_root="$HOME/.thunderbird"

[[ -d $profiles_root ]] || exit 0

while IFS= read -r -d '' prefs_file; do
    profile_dir=${prefs_file%/prefs.js}
    install -D -m 0644 \
        "$source_stylesheet" \
        "$profile_dir/chrome/userChrome.css"
done < <(find "$profiles_root" -mindepth 2 -maxdepth 2 -type f \
    -name prefs.js -print0)
