"""Run public shell entry points against disposable homes and command boundaries."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_home(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    commands = tmp_path / "bin"
    commands.mkdir()
    log = tmp_path / "calls"
    for name in ("pkexec", "pacman", "systemctl", "middleclick-autoscroll"):
        script = commands / name
        script.write_text(
            '#!/bin/bash\nprintf "%s\\n" "$0 $*" >> "$CALL_LOG"\nexit 99\n'
        )
        script.chmod(0o755)
    marker = commands / "midscroll-router"
    marker.write_text("#!/bin/bash\nexit 0\n")
    marker.chmod(0o755)
    uv = commands / "uv"
    uv.write_text(f'#!/bin/bash\nshift 4\nexec "{sys.executable}" "$@"\n')
    uv.chmod(0o755)
    return {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "XDG_CURRENT_DESKTOP": "KDE",
        "PATH": f"{commands}:{os.environ['PATH']}",
        "CALL_LOG": str(log),
    }


def invoke(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(MODULE / "install"), *args],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_leaves_home_and_commands_untouched(
    isolated_home: dict[str, str],
) -> None:
    result = invoke(isolated_home, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert not list(Path(isolated_home["HOME"]).iterdir())
    assert not Path(isolated_home["CALL_LOG"]).exists()


def test_configs_only_merges_owned_key_without_services_and_repeats(
    isolated_home: dict[str, str],
) -> None:
    config = Path(isolated_home["XDG_CONFIG_HOME"])
    config.mkdir()
    kwin = config / "kwinrc"
    kwin.write_text(
        "[Plugins]\notherEnabled=false\n\n[MouseBindings]\nCommandAll1=Move\n"
    )
    result = invoke(isolated_home, "--configs-only")
    assert result.returncode == 0, result.stderr
    assert "otherEnabled=false" in kwin.read_text()
    assert "CommandAll1=Move" in kwin.read_text()
    assert "mousetargetEnabled=true" in kwin.read_text()
    override = config / "systemd/user/midscroll-overlay.service.d/pointer-routing.conf"
    timestamp = override.stat().st_mtime_ns
    result = invoke(isolated_home, "--configs-only")
    assert result.returncode == 0, result.stderr
    assert override.stat().st_mtime_ns == timestamp
    assert not Path(isolated_home["CALL_LOG"]).exists()


def test_failed_kconfig_stage_restores_prior_files(
    isolated_home: dict[str, str],
) -> None:
    config = Path(isolated_home["XDG_CONFIG_HOME"])
    override = config / "systemd/user/midscroll-overlay.service.d/pointer-routing.conf"
    override.parent.mkdir(parents=True)
    old = b"[Service]\nExecStart=\nExecStart=%h/.local/bin/midscroll-pointer-overlay\n"
    override.write_bytes(old)
    override.chmod(0o600)
    kwin = config / "kwinrc"
    kwin.write_bytes(b"[Plugins]\nunrelated=true\n")
    before = kwin.read_bytes()
    commands = Path(isolated_home["PATH"].split(":")[0])
    python = commands / "python3"
    real_python = shutil.which("python3")
    assert real_python is not None
    python.write_text(
        "#!/bin/bash\n"
        "if [[ $1 == */apply-settings.py && $* != *--dry-run* ]]; then exit 77; fi\n"
        f'exec "{real_python}" "$@"\n'
    )
    python.chmod(0o755)
    result = invoke(isolated_home, "--configs-only")
    assert result.returncode == 77, result.stderr
    assert override.read_bytes() == old
    assert override.stat().st_mode & 0o777 == 0o600
    assert kwin.read_bytes() == before
    assert not Path(isolated_home["CALL_LOG"]).exists()


def test_unrelated_override_conflict_is_detected_before_mutation(
    isolated_home: dict[str, str],
) -> None:
    config = Path(isolated_home["XDG_CONFIG_HOME"])
    override = config / "systemd/user/midscroll-overlay.service.d/pointer-routing.conf"
    override.parent.mkdir(parents=True)
    override.write_text("[Service]\nExecStart=/my/other/helper\n")
    result = invoke(isolated_home, "--configs-only")
    assert result.returncode != 0
    assert not (config / "kwinrc").exists()
    assert not Path(isolated_home["XDG_STATE_HOME"]).exists()
    assert not Path(isolated_home["CALL_LOG"]).exists()
