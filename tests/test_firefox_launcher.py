"""Verify the legacy launcher migration in an isolated home."""
import os
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'core/config/apps/firefox/fix-no-vpn-launcher.py'


def run(home, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], env={**os.environ, 'HOME': str(home), 'XDG_CURRENT_DESKTOP': ''}, capture_output=True, text=True)


def test_existing_launcher_is_corrected_without_losing_settings(tmp_path):
    launcher = tmp_path / '.local/share/applications/firefox-no-vpn.desktop'
    launcher.parent.mkdir(parents=True)
    original = '[Desktop Entry]\nExec=/home/test/.local/bin/firefox-no-vpn %U\nStartupWMClass=firefox\nName=Firefox (No VPN)\n'
    launcher.write_text(original)
    assert run(tmp_path, '--dry-run').returncode == 0
    assert launcher.read_text() == original
    assert run(tmp_path).returncode == 0
    expected = original.replace('StartupWMClass=firefox', 'StartupWMClass=org.mozilla.firefox')
    assert launcher.read_text() == expected
    assert run(tmp_path).returncode == 0
    assert launcher.read_text() == expected


def test_missing_launcher_is_not_created(tmp_path):
    assert run(tmp_path).returncode == 0
    assert not (tmp_path / '.local/share/applications/firefox-no-vpn.desktop').exists()


def test_launcher_symlink_is_not_modified(tmp_path):
    target = tmp_path / 'original'
    target.write_text('StartupWMClass=firefox\n')
    launcher = tmp_path / '.local/share/applications/firefox-no-vpn.desktop'
    launcher.parent.mkdir(parents=True)
    launcher.symlink_to(target)
    assert run(tmp_path).returncode != 0
    assert target.read_text() == 'StartupWMClass=firefox\n'
