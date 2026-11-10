"""Exercise the folder migration in disposable homes, without system changes."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def install(
    home: Path, script: str = "core.sh", *, dry_run: bool = False
) -> subprocess.CompletedProcess[str]:
    environment = dict(
        os.environ,
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_CURRENT_DESKTOP="",
    )
    arguments = [str(ROOT / "install" / script)]
    if script == "core.sh":
        arguments.append("--configs-only")
    if dry_run:
        arguments.append("--dry-run")
    return subprocess.run(
        arguments, check=False, env=environment, capture_output=True, text=True
    )


@pytest.mark.parametrize("relative", [False, True])
def test_owned_legacy_links_relocate_after_a_read_only_dry_run(
    tmp_path: Path, relative: bool
) -> None:
    paths = {
        ".config/shell/interactive.bash": (
            "core/configs/shell/.config/shell/interactive.bash",
            "core/config/shell/files/.config/shell/interactive.bash",
        ),
        ".config/yazi/yazi.toml": (
            "core/configs/apps/.config/yazi/yazi.toml",
            "core/config/apps/yazi/files/.config/yazi/yazi.toml",
        ),
        ".local/bin/install-mouse-config": (
            "core/configs/bin/.local/bin/install-mouse-config",
            "core/commands/.local/bin/install-mouse-config",
        ),
    }
    before = {}
    for name, (old, _) in paths.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        destination = (
            (ROOT / old).relative_to(target.parent, walk_up=True)
            if relative
            else str(ROOT / old)
        )
        target.symlink_to(destination)
        before[name] = target.readlink()

    result = install(tmp_path, dry_run=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {name: (tmp_path / name).readlink() for name in paths} == before
    assert not (tmp_path / ".bashrc").exists()

    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    for name, (_, new) in paths.items():
        assert (tmp_path / name).resolve(strict=True) == ROOT / new
    assert '"editor.selectionClipboard": false' in (
        tmp_path / ".config/Code/User/settings.json"
    ).read_text(encoding="utf-8")
    result = install(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("symlink", [False, True])
def test_unmanaged_conflict_leaves_legacy_links_unchanged(
    tmp_path: Path, symlink: bool
) -> None:
    shell = tmp_path / ".config/shell/interactive.bash"
    shell.parent.mkdir(parents=True)
    original = ROOT / "core/configs/shell/.config/shell/interactive.bash"
    shell.symlink_to(original)
    conflict = tmp_path / ".config/yazi/yazi.toml"
    conflict.parent.mkdir(parents=True)
    if symlink:
        external = tmp_path / "personal.toml"
        external.write_text("# personal file\n", encoding="utf-8")
        conflict.symlink_to(external)
    else:
        conflict.write_text("# personal file\n", encoding="utf-8")

    result = install(tmp_path)
    assert result.returncode != 0
    assert shell.readlink() == original
    assert conflict.read_text(encoding="utf-8") == "# personal file\n"
    assert conflict.is_symlink() == symlink


def test_kde_install_migrates_its_links_without_installing_shell(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".config/kxkbrc"
    target.parent.mkdir(parents=True)
    target.symlink_to(ROOT / "core/configs/kde/.config/kxkbrc")
    result = install(tmp_path, "kde.sh")
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.resolve(strict=True) == ROOT / "core/config/kde/files/.config/kxkbrc"
    assert not (tmp_path / ".config/shell").exists()
