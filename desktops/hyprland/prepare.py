#!/usr/bin/env python3
"""Reconstruct the scoped desktop from pinned archives and tracked overlays."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

COMPONENT = Path(__file__).resolve().parent
REPO = COMPONENT.parents[1]
RUNTIME = Path('.local/share/dotfiles/end4-pc-trial')
MANIFEST = json.loads((COMPONENT / 'upstream.json').read_text())


def render_tree(root, home):
    for path in root.rglob('*'):
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if b'@HOME@' in data:
                path.write_bytes(data.replace(b'@HOME@', os.fsencode(home)))


def archive(cache, revision, target, paths=()):
    target.mkdir(parents=True, exist_ok=True)
    # Only these fixed, pinned repositories enter the build. No checkout hooks.
    with tempfile.TemporaryFile() as stream:
        subprocess.run(['git', '-C', str(cache), 'archive', revision, *paths],
                       stdout=stream, check=True)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as tar:
            tar.extractall(target, filter='data')


def reconstruct(target, home, caches):
    """Pure build: no downloads, user configuration writes or desktop actions."""
    config = target / 'config'
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        components = ['hypr', 'matugen', 'kitty', 'fuzzel']
        archive(caches['base'], MANIFEST['sources']['base']['commit'], temp,
                tuple('dots/.config/' + name for name in components))
        config.mkdir(parents=True)
        for name in components:
            shutil.copytree(temp / 'dots/.config' / name, config / name)
    shell = config / 'quickshell/ii'
    archive(caches['shell'], MANIFEST['sources']['shell']['commit'], shell)
    for root, patch in [(config, 'base.patch'), (shell, 'quickshell.patch')]:
        subprocess.run(['patch', '--batch', '--forward', '-p1', '-d', str(root),
                        '-i', str(COMPONENT / patch)], check=True,
                       stdout=subprocess.DEVNULL)
    shutil.copytree(REPO / 'themes/hyprland', target / 'presets')
    impulse = config / 'illogical-impulse'
    (impulse / 'presets').mkdir(parents=True)
    (impulse / 'schemes').mkdir()
    shutil.copy2(COMPONENT / 'shared/config.json', impulse / 'config.json')
    for slug, title in [('blue', 'Blue'), ('charcoal', 'Charcoal')]:
        (impulse / 'presets' / f'{title}_Anime.json').symlink_to(
            f'../../../presets/{slug}/settings.json')
        (impulse / 'schemes' / f'{slug}_anime.json').symlink_to(
            f'../../../presets/{slug}/scheme.json')
    (target / 'presets/blue/wallpaper.png').symlink_to(
        '../../assets/reference/robokoboto-blue-girl-original.png')
    (target / 'presets/charcoal/wallpaper.png').symlink_to('wallpaper-ultrawide-v1.png')
    render_tree(target, home)


def fetch_sources(home):
    caches = {}
    for name, source in MANIFEST['sources'].items():
        cache = home / '.cache/dotfiles' / source['cache']
        if not (cache / '.git').is_dir():
            cache.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--no-checkout', source['repository'], str(cache)], check=True)
        if subprocess.run(['git', '-C', str(cache), 'cat-file', '-e',
                           source['commit'] + '^{commit}'], capture_output=True).returncode:
            subprocess.run(['git', '-C', str(cache), 'fetch', '--depth', '1',
                            source['repository'], source['commit']], check=True)
        caches[name] = cache
    return caches


def fetch_assets(target, previous):
    for asset in MANIFEST['assets']:
        dest = target / asset['path']
        old = previous / asset['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        if old.is_file() and hashlib.sha256(old.read_bytes()).hexdigest() == asset['sha256']:
            shutil.copy2(old, dest)
        else:
            request = urllib.request.Request(asset['url'], headers={'User-Agent': 'dotfiles-hyprland'})
            with urllib.request.urlopen(request, timeout=60) as response:
                dest.write_bytes(response.read())
        if hashlib.sha256(dest.read_bytes()).hexdigest() != asset['sha256']:
            raise RuntimeError(f'Artwork/font checksum mismatch: {asset["path"]}')


def fingerprint():
    digest = hashlib.sha256()
    for root in [COMPONENT, REPO / 'themes/hyprland']:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                digest.update(str(path.relative_to(REPO)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def overlay_tree(source, target):
    """Replace managed paths without deleting custom presets or local extras."""
    if target.is_symlink():
        target.unlink()
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        dest = target / item.name
        if item.is_symlink():
            if dest.is_symlink() or dest.is_file():
                dest.unlink()
            dest.symlink_to(os.readlink(item))
        elif item.is_dir():
            overlay_tree(item, dest)
        else:
            if dest.is_symlink():
                dest.unlink()
            shutil.copy2(item, dest)


def generate_palette(runtime, home):
    """Use the upstream renderer directly; installation needs no compositor."""
    venv = runtime / 'venv'
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(runtime / 'config'),
               XDG_STATE_HOME=str(runtime / 'state'), XDG_CACHE_HOME=str(runtime / 'cache'),
               ILLOGICAL_IMPULSE_VIRTUAL_ENV=str(venv), GSETTINGS_BACKEND='memory')
    env['PATH'] = str(venv / 'bin') + os.pathsep + env['PATH']
    cfg = json.loads((runtime / 'config/illogical-impulse/config.json').read_text())
    palette = cfg.get('appearance', {}).get('palette', {})
    if not palette.get('namedScheme'):
        # A user-selected custom generated palette already lives in state/.
        return
    generated = runtime / 'state/quickshell/user/generated'
    generated.mkdir(parents=True, exist_ok=True)
    scripts = runtime / 'config/quickshell/ii/scripts/colors'
    subprocess.run(['python3', str(scripts / 'named_scheme.py'),
                    '--scheme', palette['namedScheme'], '--mode', 'dark',
                    '--image', cfg.get('background', {}).get('wallpaperPath', ''),
                    '--primary', palette.get('namedSchemePrimary', ''),
                    '--secondary', palette.get('namedSchemeSecondary', ''),
                    '--scss', str(generated / 'material_colors.scss'),
                    '--cache', str(generated / 'color.txt')], env=env, check=True)
    # Wait for the renderer's background terminal task before declaring success.
    subprocess.run(['bash', '-c', 'source "$1"; wait', 'bash', str(scripts / 'applycolor.sh')],
                   env=env, check=True)


def install(home, adopt_trial=False):
    runtime = home / RUNTIME
    marker = runtime / '.dotfiles-managed'
    loader = home / '.config/hypr/hyprland.lua'
    if runtime.exists() and not marker.exists() and not adopt_trial:
        raise RuntimeError('Existing trial: use --adopt-trial to back up and adopt it.')
    if loader.exists() and 'dotfiles/end4-pc-trial/config/hypr/' not in loader.read_text():
        raise RuntimeError(f'Refusing unrelated Hyprland startup: {loader}')
    stamp = fingerprint()
    if marker.exists() and marker.read_text().strip() == stamp:
        print('Hyprland configuration already installed; saved theme/preferences preserved.')
        return
    caches = fetch_sources(home)
    runtime.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hyprland-build-', dir=runtime.parent) as temp:
        build = Path(temp)
        reconstruct(build, home, caches)
        fetch_assets(build, runtime)
        # Mutable settings and selected theme belong to the running shell, never Git.
        current = runtime / 'config/illogical-impulse/config.json'
        if current.exists():
            json.loads(current.read_text())  # Refuse invalid state before installation.
            shutil.copy2(current, build / 'config/illogical-impulse/config.json')
        # Keep the selected scheme's existing generated palettes until native reload.
        for relative in ['hypr/hyprland/colors.lua', 'hypr/hyprlock/colors.conf',
                         'fuzzel/fuzzel_theme.ini']:
            source = runtime / 'config' / relative
            if source.exists():
                shutil.copy2(source, build / 'config' / relative)
        if runtime.exists():
            backup_root = home / '.local/state/dotfiles/hyprland/backups'
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = Path(tempfile.mkdtemp(prefix='before-install-', dir=backup_root))
            for name in ['config', 'presets']:
                if (runtime / name).exists():
                    shutil.copytree(runtime / name, backup / name, symlinks=True)
            if loader.exists():
                shutil.copy2(loader, backup / 'hyprland.lua')
            print(f'Previous configuration backup: {backup}')
        runtime.mkdir(exist_ok=True)
        for name in ['config', 'presets']:
            overlay_tree(build / name, runtime / name)
        shutil.copytree(build / 'assets', runtime / 'assets', dirs_exist_ok=True)
    venv = runtime / 'venv'
    if not (venv / 'bin/python').exists():
        subprocess.run(['uv', 'venv', str(venv)], check=True)
    subprocess.run(['uv', 'pip', 'install', '--python', str(venv / 'bin/python'),
                    '-r', str(COMPONENT / 'shared/requirements.txt')], check=True)
    font_dir = home / '.local/share/fonts/end-4-trial'
    font_dir.mkdir(parents=True, exist_ok=True)
    for font in (runtime / 'assets/fonts').glob('*.ttf'):
        shutil.copy2(font, font_dir / font.name)
    subprocess.run(['fc-cache', str(font_dir)], check=True)
    bin_dir = home / '.local/bin'
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ['end4-pc-trial', 'end4-pc-terminal', 'end-4-snap']:
        shutil.copy2(COMPONENT / 'shared' / name, bin_dir / name)
    app_dir = home / '.local/share/applications'
    app_dir.mkdir(parents=True, exist_ok=True)
    for path in (COMPONENT / 'shared/applications').glob('*.desktop'):
        (app_dir / path.name).write_text(path.read_text().replace('@HOME@', str(home)))
    loader.parent.mkdir(parents=True, exist_ok=True)
    loader.write_text('-- Managed by dotfiles desktops/hyprland.\n'
                      'local base=os.getenv("HOME") .. "/.local/share/dotfiles/end4-pc-trial/config/hypr/"\n'
                      'package.path=base .. "?.lua;" .. base .. "?/init.lua;" .. package.path\n'
                      'dofile(base .. "hyprland.lua")\n')
    generate_palette(runtime, home)
    marker.write_text(stamp + '\n')
    print('Hyprland saved and installed. Existing theme/state retained; no session restarted.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adopt-trial', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.dry_run:
        print('Would reconstruct pinned end-4/End4-pC with tracked patches and two presets.')
        print('Would back up owned config, preserve saved theme/state, and install scoped launchers.')
        print('No packages, KDE settings, Neovim, credentials or sessions would be changed.')
    else:
        install(Path.home(), args.adopt_trial)
