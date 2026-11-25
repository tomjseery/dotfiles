#!/usr/bin/env python3
"""Correct the legacy Flatpak launcher if it claims native Firefox windows."""
import argparse
import os
import shutil
import subprocess
from pathlib import Path
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dry-run', action='store_true')
args = parser.parse_args()
launcher = Path.home() / '.local/share/applications/firefox-no-vpn.desktop'
if launcher.is_symlink():
    raise SystemExit(f'Refusing to edit launcher symlink: {launcher}')
if launcher.exists():
    original = launcher.read_text()
    old = 'StartupWMClass=firefox\n'
    if old in original and any(line.startswith('Exec=') and 'firefox-no-vpn' in line
                               for line in original.splitlines()):
        result = original.replace(old, 'StartupWMClass=org.mozilla.firefox\n', 1)
        print(f"{'Would update' if args.dry_run else 'Update'} {launcher}")
        if not args.dry_run:
            fd, temporary = tempfile.mkstemp(prefix='.dotfiles-', dir=launcher.parent)
            try:
                with os.fdopen(fd, 'w') as output:
                    output.write(result)
                os.chmod(temporary, launcher.stat().st_mode & 0o777)
                os.replace(temporary, launcher)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":"):
                refresh = shutil.which("kbuildsycoca6")
                if refresh:
                    subprocess.run([refresh], check=True)
