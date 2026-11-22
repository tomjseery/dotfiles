#!/usr/bin/env python3
"""Apply the shared icon choice without replacing unrelated application settings."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('dotfiles_settings', ROOT / 'scripts/apply-settings.py')
settings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(settings)


def choice():
    data = json.loads((Path(__file__).parent / 'theme.json').read_text())
    if not all(re.fullmatch(r'[A-Za-z0-9_.+-]+', data[k]) for k in ['name', 'package']):
        raise ValueError('Invalid icon theme/package name')
    return data


def apply(home, dry_run=False):
    name = choice()['name']
    config = home / '.config'
    fragment = f'[Icons]\nTheme={name}\n'
    changes = [(config / 'kdeglobals', settings.merge_kconfig, fragment)]
    launcher = home / '.local/share/applications/vesktop.desktop'
    system_launcher = Path('/usr/share/applications/vesktop.desktop')
    if launcher.exists() or system_launcher.exists():
        if launcher.is_symlink():
            raise ValueError(f'Refusing to replace a launcher symlink: {launcher}')
        original = launcher.read_text() if launcher.exists() else ''
        generated = not original or 'X-Dotfiles-Generated=true' in original
        if generated and system_launcher.exists():
            original = system_launcher.read_text()
        overlay = '[Desktop Entry]\nIcon=discord\n'
        if generated:
            overlay += 'X-Dotfiles-Generated=true\n'
        changes.append((launcher, lambda _original, value: settings.merge_kconfig(original, value), overlay))
    for version in ['3.0', '4.0']:
        changes.append((config / f'gtk-{version}/settings.ini', settings.merge_kconfig,
                        f'[Settings]\ngtk-icon-theme-name={name}\n'))
    runtime = home / '.local/share/dotfiles/end4-pc-trial/config'
    user_config = runtime / 'illogical-impulse/config.json'
    if user_config.exists():
        changes.append((runtime / 'kdeglobals', settings.merge_kconfig, fragment))
        overlay = {'appearance': {'icons': {'theme': name, 'followScheme': False, 'dynamicColor': False}}}
        changes.append((user_config, settings.merge_json, json.dumps(overlay)))
    # Validate all targets before making any writes.
    pending = []
    for path, merge, overlay in changes:
        if path.is_symlink():
            raise ValueError(f'Refusing to replace a settings symlink: {path}')
        before = path.read_text() if path.exists() else ''
        after = merge(before, overlay)
        if before != after:
            pending.append((path, after))
    for path, content in pending:
        print(f'{"Would update" if dry_run else "Update"} {path}')
        if dry_run:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.icons-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(content)
            os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o600)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--package', action='store_true')
    args = parser.parse_args()
    if args.package:
        print(choice()['package'])
    else:
        apply(Path.home(), args.dry_run)
