#!/usr/bin/env python3
"""Capture both presets and test startup in an isolated temporary home.

Requires the installed desktop, pinned source caches, bat, g++ and grim. Run in a
separate D-Bus session: dbus-run-session -- python3 desktops/hyprland/preview.py.
Never applies presets to, restores, or writes the real user's configuration.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import sys
import prepare


def wait_until(check, message, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(.2)
    raise RuntimeError(message)


def stop_owned(home):
    """Only processes whose HOME is our private temporary directory."""
    expected = os.fsencode('HOME=' + str(home))
    owned = []
    for path in Path('/proc').glob('[0-9]*/environ'):
        try:
            if expected in path.read_bytes().split(b'\0'):
                owned.append(int(path.parent.name))
        except (PermissionError, ProcessLookupError, FileNotFoundError):
            pass
    for pid in owned:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def main(output):
    real_home = Path.home()
    live = real_home / prepare.RUNTIME
    live_config = live / 'config/illogical-impulse/config.json'
    protected = [live_config, live / 'state/quickshell/user/generated/colors.json',
                 live / 'state/quickshell/user/generated/terminal/kitty-theme.conf']
    original = {path: path.read_bytes() for path in protected if path.exists()}
    output.mkdir(parents=True, exist_ok=True)
    caches = {k: real_home / '.cache/dotfiles' / v['cache']
              for k, v in prepare.MANIFEST['sources'].items()}
    with tempfile.TemporaryDirectory(prefix='dotfiles-hyprland-preview-') as directory:
        home = Path(directory)
        runtime = home / prepare.RUNTIME
        prepare.reconstruct(runtime, home, caches)
        # Share only immutable artwork/dependencies, not state or credentials.
        (runtime / 'assets').symlink_to(live / 'assets', target_is_directory=True)
        (runtime / 'venv').symlink_to(live / 'venv', target_is_directory=True)
        fonts = home / '.local/share/fonts'
        fonts.parent.mkdir(parents=True, exist_ok=True)
        fonts.symlink_to(real_home / '.local/share/fonts', target_is_directory=True)
        bin_dir = home / '.local/bin'
        bin_dir.mkdir(parents=True)
        for name in ['end4-pc-trial', 'end4-pc-terminal', 'end-4-snap']:
            shutil.copy2(prepare.COMPONENT / 'shared' / name, bin_dir / name)
        secret_tool = bin_dir / 'secret-tool'
        secret_tool.write_text('#!/usr/bin/env bash\nexit 1\n')
        secret_tool.chmod(0o755)
        loader = home / '.config/hypr/hyprland.lua'
        loader.parent.mkdir(parents=True)
        loader.write_text('local base=os.getenv("HOME") .. "/.local/share/dotfiles/end4-pc-trial/config/hypr/"\n'
                          'package.path=base .. "?.lua;" .. base .. "?/init.lua;" .. package.path\n'
                          'dofile(base .. "hyprland.lua")\n'
                          'hl.monitor({output="",mode="2560x1080@60",position="auto",scale=1})\n')
        # Socket updates and temporary-image cleanup must never reach a live
        # desktop/terminal, even though both run as the same Unix user.
        socket_prefix = 'end4pc-preview-' + home.name[-8:] + '-kitty-'
        for path in [bin_dir / 'end4-pc-terminal',
                     runtime / 'config/quickshell/ii/scripts/colors/applycolor.sh']:
            path.write_text(path.read_text().replace('end4pc-kitty-', socket_prefix))
        directories = runtime / 'config/quickshell/ii/modules/common/Directories.qml'
        directories.write_text(directories.read_text().replace('/tmp/quickshell', str(home / 'quickshell-temp')))
        # Version stamps avoid irrelevant first-run compositor news dialogs.
        for name in ['lastVersion', 'lastNag']:
            stamp = real_home / '.local/share/hyprland' / name
            if stamp.is_file():
                target = home / '.local/share/hyprland' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stamp, target)
        # Preview needs no provider keys. Do not contact any real secret service.
        lookup = runtime / 'config/quickshell/ii/scripts/keyring/try_lookup.sh'
        lookup.write_text('#!/usr/bin/env bash\nprintf "not found\\n"\nexit 1\n')
        # Keep the real startup path, but never import a nested display into the
        # host's user systemd environment. D-Bus itself is isolated by the caller.
        execs = runtime / 'config/hypr/hyprland/execs.lua'
        execs.write_text(execs.read_text().replace(' --systemd ', ' '))
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                   XDG_STATE_HOME=str(home / '.local/state'), XDG_CACHE_HOME=str(home / '.cache'),
                   XDG_DATA_HOME=str(home / '.local/share'), AQ_DRM_DEVICES='/dev/null',
                   HYPRLAND_NO_SD_VARS='1', HYPRLAND_NO_SD_NOTIFY='1', XDG_CURRENT_DESKTOP='Hyprland')
        env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
        env['PATH'] = str(bin_dir) + os.pathsep + env['PATH']
        scoped = dict(env, XDG_CONFIG_HOME=str(runtime / 'config'),
                      XDG_STATE_HOME=str(runtime / 'state'), XDG_CACHE_HOME=str(runtime / 'cache'),
                      GSETTINGS_BACKEND='memory', ILLOGICAL_IMPULSE_VIRTUAL_ENV=str(runtime / 'venv'))
        scoped['PATH'] = str(runtime / 'venv/bin') + os.pathsep + scoped['PATH']
        config = runtime / 'config/illogical-impulse/config.json'
        cfg = json.loads(config.read_text())
        # This is exclusively the temporary profile. Keep desktop screenshots
        # free of optional weather/AI requests and wallpaper-upscale notices.
        cfg['background']['widgets']['clock']['cookie']['aiStyling'] = False
        config.write_text(json.dumps(cfg))
        demo = home / 'cpp-workspace'
        demo.mkdir()
        (demo / 'main.cpp').write_text('#include <array>\n#include <iostream>\n#include <numeric>\n\n'
            'int main() {\n    constexpr std::array tasks{3, 5, 8};\n'
            '    const auto total = std::accumulate(tasks.begin(), tasks.end(), 0);\n'
            '    std::cout << "Hello, Hyprland\\n";\n'
            '    std::cout << "Ready to build: " << total << " tasks\\n";\n}\n')
        script = demo / 'terminal.sh'
        script.write_text('set -eu\nprintf "\\n  KITTY / C++ WORKSPACE\\n\\n"\n'
            'bat --color=always --paging=never --style=numbers --theme=ansi main.cpp\n'
            'printf "\\n$ g++ -std=c++20 -Wall -Wextra main.cpp -o demo\\n"\n'
            'g++ -std=c++20 -Wall -Wextra main.cpp -o demo\n'
            'printf "$ ./demo\\n\\n"\n./demo\n'
            'export PS1="cpp-workspace $ "\nexec bash --noprofile --norc\n')
        def select(title):
            subprocess.run(['bash', str(runtime / 'config/quickshell/ii/scripts/presets.sh'),
                            '--apply', title + '_Anime'], env=scoped, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Both complete starts must preserve a preselected, non-default profile.
        # Then a native switch to Blue must survive another full compositor start.
        select('Charcoal')
        for attempt, title in enumerate(['Charcoal', 'Charcoal', 'Blue']):
            slug = title.lower()
            with (output / f'{slug}-startup.log').open('a') as log:
                compositor = subprocess.Popen(['start-hyprland', '--', '--config', str(loader)], env=env,
                                               stdout=log, stderr=log, start_new_session=True)
                try:
                    def instance():
                        if compositor.poll() is not None:
                            raise RuntimeError('Nested compositor stopped; inspect startup log')
                        result = subprocess.run(['hyprctl', 'instances', '-j'], env=env,
                                                capture_output=True, text=True)
                        try:
                            for item in json.loads(result.stdout):
                                try:
                                    data = Path(f'/proc/{item["pid"]}/environ').read_bytes()
                                    if os.fsencode('HOME=' + str(home)) in data.split(b'\0'):
                                        return item
                                except (PermissionError, ProcessLookupError, FileNotFoundError):
                                    pass
                            return None
                        except (ValueError, TypeError):
                            return None
                    inst = wait_until(instance, 'No nested compositor IPC')
                    active = dict(env, HYPRLAND_INSTANCE_SIGNATURE=inst['instance'], WAYLAND_DISPLAY=inst['wl_socket'])
                    scoped.update(HYPRLAND_INSTANCE_SIGNATURE=inst['instance'], WAYLAND_DISPLAY=inst['wl_socket'])
                    def shell_ready():
                        return subprocess.run([str(bin_dir / 'end4-pc-trial'), 'ipc', 'call', 'settings', 'close'],
                                              env=active, capture_output=True).returncode == 0
                    wait_until(shell_ready, 'Production startup did not launch shell')
                    time.sleep(3)
                    actual = json.loads(config.read_text())
                    assert actual['appearance']['palette']['namedScheme'] == slug + '_anime'
                    colors = json.loads((runtime / 'state/quickshell/user/generated/colors.json').read_text())
                    assert colors['surface'].lower() == ('#24262e' if slug == 'charcoal' else '#0c1220')
                    errors = subprocess.check_output(['hyprctl', 'configerrors'], env=active, text=True).strip()
                    assert errors in ['', 'ok'], errors
                    subprocess.run(['grim', str(output / f'{slug}-desktop.png')], env=active, check=True)
                    terminal = subprocess.Popen([str(bin_dir / 'end4-pc-terminal'), '--', 'bash', '--noprofile',
                                                 '--norc', str(script)], cwd=demo, env=active, stdout=log, stderr=log)
                    time.sleep(3)
                    assert terminal.poll() is None, 'Demo terminal failed'
                    subprocess.run([str(bin_dir / 'end-4-snap'), 'right'], env=active, check=True)
                    time.sleep(1)
                    subprocess.run(['grim', str(output / f'{slug}-terminal.png')], env=active, check=True)
                    print(f'PASS full Hyprland startup retained {title}', flush=True)
                    if attempt == 1:
                        select('Blue')
                        time.sleep(2)
                finally:
                    stop_owned(home)
                    try:
                        compositor.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        compositor.kill(); compositor.wait()
        for path, content in original.items():
            assert path.read_bytes() == content, f'Live state changed outside the isolated preview: {path.name}'
        print('PASS live theme/config/palettes remained byte-for-byte unchanged; no restore operation', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/dotfiles-hyprland-gallery'))
    args = parser.parse_args()
    if os.environ.get('DOTFILES_PREVIEW_DBUS') != '1':
        # Self-isolate even when called without the documented D-Bus wrapper.
        child_env = dict(os.environ, DOTFILES_PREVIEW_DBUS='1')
        raise SystemExit(subprocess.call(['dbus-run-session', '--', sys.executable,
                         str(Path(__file__).resolve()), '--output', str(args.output.resolve())],
                         env=child_env))
    main(args.output.resolve())
