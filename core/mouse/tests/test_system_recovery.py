"""Rehearse root-stage failure in a private user namespace with fake package I/O."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1]


@pytest.fixture(params=[False, True], ids=["working-checkout", "temporary-checkout"])
def module_path(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    if not request.param:
        return MODULE
    module = tmp_path_factory.mktemp("relocated-checkout") / "core/mouse"
    module.mkdir(parents=True)
    shutil.copy2(MODULE / "install", module / "install")
    for relative in ("src/midscroll_routing", "system", "package/usr/share"):
        shutil.copytree(MODULE / relative, module / relative)
    return module


@pytest.mark.parametrize("fail_restart", [True, False])
def test_system_failure_or_manual_recovery_restores_state(
    tmp_path: Path, fail_restart: bool, module_path: Path
) -> None:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        pytest.skip("Root recovery rehearsal requires bubblewrap user namespaces")
    library = tmp_path / "lib"
    library.mkdir()
    for entry in Path("/usr/lib").iterdir():
        if (entry / "libxul.so").is_file():
            continue
        if entry.name not in {"python3.14", "qt6", "hyprland"}:
            (library / entry.name).symlink_to(Path("/opt/lib") / entry.name)
    python = library / "python3.14"
    python.mkdir()
    for entry in Path("/usr/lib/python3.14").iterdir():
        if entry.name != "site-packages":
            (python / entry.name).symlink_to(Path("/opt/lib/python3.14") / entry.name)
    shutil.copytree(
        module_path / "src/midscroll_routing",
        python / "site-packages/midscroll_routing",
    )
    share = tmp_path / "share"
    shutil.copytree(module_path / "package/usr/share", share)
    etc = tmp_path / "etc"
    etc.mkdir()
    prior = b"DEADZONE_PX = 42\nNATIVE_DEFAULT = false\nFALLBACK_APPS = original\n"
    (etc / "midscroll.conf").write_bytes(prior)
    (etc / "midscroll.conf").chmod(0o600)
    state = tmp_path / "var"
    state.mkdir()
    commands = tmp_path / "bin"
    commands.mkdir()
    pacman = commands / "pacman"
    pacman.write_text(
        '#!/bin/bash\nprintf "pacman %s\\n" "$*" >> /var/events\n'
        'case $1 in -Q|-Qp) echo "midscroll 1.15-1";; -U) exit 0;; *) exit 90;; esac\n'
    )
    systemctl = commands / "systemctl"
    systemctl.write_text(
        '#!/bin/bash\nprintf "systemctl %s\\n" "$*" >> /var/events\n'
        "case $1 in is-active) exit 0;; is-enabled) echo disabled; exit 1;; restart)\n"
        "if [[ ! -e /var/failed-once ]]; then\n"
        "  touch /var/failed-once; exit 73; fi;; esac\n"
    )
    if not fail_restart:
        systemctl.write_text(systemctl.read_text().replace("exit 73", "true"))
    pacman.chmod(0o755)
    systemctl.chmod(0o755)
    package = tmp_path / "package"
    package.write_bytes(b"fake-package-boundary")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "package": str(package),
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            }
        )
    )
    bridges = tmp_path / "bridges"
    bridges.mkdir()
    for name in ("mousetarget.so", "mouse_target_hyprland.so"):
        (bridges / name).write_bytes(b"fake-bridge-boundary")
    result = subprocess.run(
        [
            bwrap,
            "--unshare-all",
            "--uid",
            "0",
            "--gid",
            "0",
            "--ro-bind",
            "/",
            "/",
            "--ro-bind",
            "/usr",
            "/opt",
            "--bind",
            str(library),
            "/usr/lib",
            "--bind",
            str(share),
            "/usr/share",
            "--bind",
            str(etc),
            "/etc",
            "--bind",
            str(state),
            "/var",
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(tmp_path),
            str(tmp_path),
            "--ro-bind",
            str(module_path),
            str(module_path),
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "--setenv",
            "PATH",
            f"{commands}:/usr/bin",
            "--",
            str(module_path / "install"),
            "--system",
            str(manifest),
            str(manifest),
            str(bridges),
        ],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if fail_restart:
        assert result.returncode == 73, result.stderr
        assert "restoring" in result.stderr
        assert "Automatic recovery failed" not in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "NATIVE_DEFAULT = true" in (etc / "midscroll.conf").read_text()
        assert "DEADZONE_PX = 42" in (etc / "midscroll.conf").read_text()
        backup = (state / "lib/dotfiles-mouse/last-recovery").read_text().strip()
        args = list(result.args)
        args[args.index("--system") :] = ["--system-recover", backup]
        recovered = subprocess.run(args, text=True, capture_output=True, check=False)
        assert recovered.returncode == 0, recovered.stderr
    assert (etc / "midscroll.conf").read_bytes() == prior
    assert (etc / "midscroll.conf").stat().st_mode & 0o777 == 0o600
    assert not (etc / "systemd/system/midscroll.service.d/native-default.conf").exists()
    assert not (library / "qt6/plugins/kwin/effects/plugins/mousetarget.so").exists()
    assert not (library / "hyprland/plugins/mouse_target_hyprland.so").exists()
    events = (state / "events").read_text()
    assert events.count("pacman -U") == 2
    assert "systemctl disable midscroll.service" in events
    assert events.count("systemctl restart midscroll.service") == 2
