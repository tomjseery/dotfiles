#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
exec pkexec "$repo_root/core/configs/bin/.local/bin/finish-arch-setup" "$@"
