"""Exercise Plasma launcher repairs with disposable XDG application directories."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "desktops/kde/launcher-identity.py"


@pytest.fixture
def applications(tmp_path):
    user = tmp_path / "user" / "applications"
    system = tmp_path / "system" / "applications"
    user.mkdir(parents=True)
    system.mkdir(parents=True)
    return user, system


def check(applications, *actions):
    user, system = applications
    environment = {
        **os.environ,
        "XDG_DATA_HOME": str(user.parent),
        "XDG_DATA_DIRS": str(system.parent),
        "XDG_CURRENT_DESKTOP": "",
    }
    return subprocess.run(
        [sys.executable, str(CHECKER), *actions],
        env=environment, capture_output=True, text=True,
    )


def entry(name, hint=""):
    return f"[Desktop Entry]\nType=Application\nName={name}\nExec=/usr/bin/true\n{hint}"


def test_discovery_respects_user_overrides_and_hidden_entries(applications):
    user, system = applications
    (system / "org.example.Paint.desktop").write_text(entry("Paint"))
    (system / "other.desktop").write_text(entry("Other", "StartupWMClass=org.example.Paint\n"))
    (user / "other.desktop").write_text(entry("Other", "Hidden=true\n"))
    (user / "alternate.desktop").write_text(entry("Alternate", "StartupWMClass=ORG.EXAMPLE.PAINT\n"))
    result = check(applications)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "org.example.paint: alternate.desktop, org.example.Paint.desktop\n"


def test_repairs_only_the_main_group_and_stops_reporting_the_conflict(applications):
    user, system = applications
    (system / "org.example.Editor.desktop").write_text(entry("Editor"))
    alias = user / "alternate.desktop"
    original = entry("Alternate", "StartupWMClass=org.example.Editor\n")
    action = "\n[Desktop Action Test]\nStartupWMClass=org.example.Editor\n"
    alias.write_bytes((original + action).replace("\n", "\r\n").encode())

    result = check(applications, "--set-class", alias.name, "org.example.Alternate")
    assert result.returncode == 0, result.stderr
    expected = original.replace("org.example.Editor", "org.example.Alternate") + action
    assert alias.read_bytes() == expected.replace("\n", "\r\n").encode()
    assert check(applications).stdout == ""
    assert check(applications, "--set-class", alias.name, "org.example.Alternate").stdout == ""


def test_clear_class_creates_a_user_override_for_a_packaged_launcher(applications):
    user, system = applications
    original = system / "org.example.Alternate.desktop"
    content = entry("Alternate", "StartupWMClass=org.example.Player\n")
    original.write_text(content)
    (system / "org.example.Player.desktop").write_text(entry("Player"))

    assert check(applications).stdout
    result = check(applications, "--clear-class", original.name)
    assert result.returncode == 0, result.stderr
    assert original.read_text() == content
    assert (user / original.name).read_text() == entry("Alternate")
    assert check(applications).stdout == ""


def test_refuses_a_new_collision_and_symlink_replacement(applications):
    user, system = applications
    (system / "org.example.Editor.desktop").write_text(entry("Editor"))
    original = system / "other.desktop"
    original.write_text(entry("Other"))
    assert check(applications, "--set-class", original.name, "org.example.Editor").returncode == 1
    alias = user / original.name
    alias.symlink_to(original)
    assert check(applications, "--set-class", alias.name, "alternate").returncode == 1
    assert alias.is_symlink()
    assert original.read_text() == entry("Other")
