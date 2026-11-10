import base64
import json
import stat
from pathlib import Path

import pytest

from midscroll_routing import installation

PROFILE = "NATIVE_DEFAULT = true\nFALLBACK_APPS = kitty, org.kde.konsole\n"


def runtime(root: Path, name: str = "future-browser") -> Path:
    directory = root / "usr/lib" / name
    (directory / "browser").mkdir(parents=True)
    for marker in ("libxul.so", "application.ini", "browser/omni.ja"):
        (directory / marker).touch()
    return directory / "browser/defaults/preferences/zz-dotfiles-mouse.js"


def test_merge_policy_preserves_unowned_settings_and_line_endings() -> None:
    existing = (
        "# a comment\r\nSPEED_MULT = 1.23 # custom\r\n"
        "NATIVE_DEFAULT = false\r\nFALLBACK_APPS = old\r\n"
        "IGNORE_DEVICES = custom-device"
    )
    result = installation.merge_policy(existing, PROFILE)
    assert result.startswith("# a comment\r\nSPEED_MULT = 1.23 # custom\r\n")
    assert "IGNORE_DEVICES = custom-device\n" in result
    assert "NATIVE_DEFAULT = true\n" in result
    assert "FALLBACK_APPS = kitty, org.kde.konsole\n" in result
    assert installation.merge_policy(result, PROFILE) == result


@pytest.mark.parametrize(
    "profile",
    [
        "FALLBACK_APPS = kitty\n",
        "NATIVE_DEFAULT = false\nFALLBACK_APPS = kitty\n",
        PROFILE + "NATIVE_DEFAULT = true\n",
        "NATIVE_DEFAULT = true\nFALLBACK_APPS = kitty,,invalid\n",
        "NATIVE_DEFAULT = true\nFALLBACK_APPS = kitty;command\n",
    ],
)
def test_merge_policy_rejects_invalid_owned_profile(profile: str) -> None:
    with pytest.raises(ValueError):
        installation.merge_policy("unrelated=true\n", profile)


def test_configure_system_preserves_other_values_and_existing_mode(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "usr/share/midscroll/native-default.conf"
    profile.parent.mkdir(parents=True)
    profile.write_text(PROFILE, encoding="utf-8")
    config = tmp_path / "etc/midscroll.conf"
    config.parent.mkdir()
    config.write_text("SPEED_MULT = 12\nBLACKLIST = old\n", encoding="utf-8")
    config.chmod(0o600)
    installation.configure_system(tmp_path, config)
    before = config.stat().st_mtime_ns
    installation.configure_system(tmp_path, config)
    assert config.stat().st_mtime_ns == before
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert config.read_text(encoding="utf-8").startswith(
        "SPEED_MULT = 12\nBLACKLIST = old\n"
    )


def test_snapshot_restore_preserves_bytes_modes_and_missing_files(
    tmp_path: Path,
) -> None:
    original = tmp_path / "etc/owned"
    original.parent.mkdir()
    original.write_bytes(b"\x00original\xff")
    original.chmod(0o640)
    backup = tmp_path / "backup.json"
    installation.snapshot(tmp_path, ["etc/owned", "etc/missing"], backup)
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    original.write_bytes(b"changed")
    original.chmod(0o777)
    (tmp_path / "etc/missing").write_bytes(b"new")
    installation.restore(tmp_path, backup)
    assert original.read_bytes() == b"\x00original\xff"
    assert stat.S_IMODE(original.stat().st_mode) == 0o640
    assert not (tmp_path / "etc/missing").exists()
    installation.restore(tmp_path, backup)


@pytest.mark.parametrize(
    "bad_entry",
    [
        {"data": "invalid base64", "mode": 0o644},
        {"data": "", "mode": True},
        {"data": "", "mode": -1},
        {"data": None, "mode": 0o644},
        {"data": "", "mode": 0o644, "extra": 1},
    ],
)
def test_restore_validates_every_entry_before_writing(
    tmp_path: Path, bad_entry: object
) -> None:
    first = tmp_path / "first"
    first.write_bytes(b"unchanged")
    backup = tmp_path / "backup.json"
    backup.write_text(
        json.dumps(
            {
                "first": {
                    "data": base64.b64encode(b"restored").decode(),
                    "mode": 0o644,
                },
                "last": bad_entry,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        installation.restore(tmp_path, backup)
    assert first.read_bytes() == b"unchanged"


@pytest.mark.parametrize("relative", ["../escape", "/absolute", ".", ""])
def test_safe_path_rejects_escaping_or_empty_paths(
    tmp_path: Path, relative: str
) -> None:
    with pytest.raises(ValueError):
        installation.safe_path(tmp_path, relative)


def test_snapshot_rejects_internal_symlinks_and_leaves_backup_absent(
    tmp_path: Path,
) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    backup = tmp_path / "backup.json"
    with pytest.raises(ValueError, match="symlink"):
        installation.snapshot(tmp_path, ["link/file"], backup)
    assert not backup.exists()


def test_restore_rejects_later_symlink_before_restoring_first_file(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    first.write_bytes(b"unchanged")
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    backup = tmp_path / "backup.json"
    data = {"data": base64.b64encode(b"restored").decode(), "mode": 0o644}
    backup.write_text(json.dumps({"first": data, "link/last": data}), encoding="utf-8")
    with pytest.raises(ValueError, match="symlink"):
        installation.restore(tmp_path, backup)
    assert first.read_bytes() == b"unchanged"
    assert not (real / "last").exists()


def test_restore_rejects_conflicting_paths_before_writes(tmp_path: Path) -> None:
    backup = tmp_path / "backup.json"
    data = {"data": "", "mode": 0o644}
    backup.write_text(json.dumps({"a": data, "a/b": data}), encoding="utf-8")
    with pytest.raises(ValueError, match="Overlapping"):
        installation.restore(tmp_path, backup)
    assert not (tmp_path / "a").exists()


def test_snapshot_rejects_backup_overlapping_an_owned_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="overlaps"):
        installation.snapshot(tmp_path, ["owned"], tmp_path / "owned/backup.json")
    assert not (tmp_path / "owned").exists()


def test_restore_rejects_aliased_paths_before_writes(tmp_path: Path) -> None:
    backup = tmp_path / "backup.json"
    data = {"data": "", "mode": 0o644}
    backup.write_text(json.dumps({"a": data, "./a": data}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        installation.restore(tmp_path, backup)
    assert not (tmp_path / "a").exists()


def test_replace_file_is_idempotent_and_failed_rename_retains_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "owned"
    installation.replace_file(target, b"old", 0o600)
    before = target.stat().st_mtime_ns
    installation.replace_file(target, b"old", 0o600)
    assert target.stat().st_mtime_ns == before

    def failed_replace(self: Path, target: Path) -> Path:
        raise OSError("rename failed")

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="rename failed"):
        installation.replace_file(target, b"new")
    assert target.read_bytes() == b"old"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert set(tmp_path.iterdir()) == {target}


def test_native_defaults_use_application_preferences_and_restore_cleanly(
    tmp_path: Path,
) -> None:
    target = runtime(tmp_path)
    target.parent.mkdir(parents=True)
    unrelated = target.parent / "unrelated.js"
    unrelated.write_bytes(b'pref("unrelated", true);\n')
    backup = tmp_path / "native-backup.json"
    installation.configure_native_defaults(tmp_path, backup)
    assert target.read_bytes() == installation.NATIVE_PREFS
    assert unrelated.read_bytes() == b'pref("unrelated", true);\n'
    assert not (
        tmp_path / "usr/lib/future-browser/defaults/pref/zz-dotfiles-mouse.js"
    ).exists()
    before, saved = target.stat().st_mtime_ns, backup.read_bytes()
    installation.configure_native_defaults(tmp_path, backup)
    assert target.stat().st_mtime_ns == before
    assert backup.read_bytes() == saved
    installation.restore(tmp_path, backup)
    assert not target.exists()
    assert unrelated.exists()


def test_native_defaults_conflict_is_found_before_any_mutation(tmp_path: Path) -> None:
    first = runtime(tmp_path, "a-browser")
    second = runtime(tmp_path, "z-browser")
    second.parent.mkdir(parents=True)
    second.write_bytes(b'pref("other", true);\n')
    backup = tmp_path / "backup.json"
    with pytest.raises(FileExistsError, match="Unrelated"):
        installation.configure_native_defaults(tmp_path, backup)
    assert not first.exists()
    assert not backup.exists()
    assert second.read_bytes() == b'pref("other", true);\n'


def test_native_defaults_validation_does_not_create_directories(tmp_path: Path) -> None:
    target = runtime(tmp_path)
    installation.validate_native_defaults(tmp_path)
    assert not target.parent.exists()
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unrelated")
    with pytest.raises(FileExistsError, match="Unrelated"):
        installation.validate_native_defaults(tmp_path)
    assert target.read_bytes() == b"unrelated"


def test_native_defaults_updates_only_owned_file_and_snapshots_before_failed_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = runtime(tmp_path, "a-browser"), runtime(tmp_path, "z-browser")
    first.parent.mkdir(parents=True)
    original = installation.NATIVE_PREFS_HEADER + b" previous version\n"
    first.write_bytes(original)
    first.chmod(0o600)
    backup = tmp_path / "backup.json"
    real_replace = Path.replace

    def failing_second_replace(self: Path, target: Path) -> Path:
        if target == second:
            raise OSError("staged write failure")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_second_replace)
    with pytest.raises(OSError, match="staged write failure"):
        installation.configure_native_defaults(tmp_path, backup)
    assert backup.exists()
    assert first.read_bytes() == installation.NATIVE_PREFS
    assert not second.exists()
    installation.restore(tmp_path, backup)
    assert first.read_bytes() == original
    assert stat.S_IMODE(first.stat().st_mode) == 0o600


def test_native_defaults_ignores_incomplete_runtime_without_browser_exceptions(
    tmp_path: Path,
) -> None:
    partial = tmp_path / "usr/lib/new-engine"
    partial.mkdir(parents=True)
    (partial / "libxul.so").touch()
    backup = tmp_path / "backup.json"
    installation.configure_native_defaults(tmp_path, backup)
    assert not backup.exists()
    assert not (partial / "browser/defaults/preferences").exists()
