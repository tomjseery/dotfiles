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


def cursor_source(tmp_path: Path) -> Path:
    source = tmp_path / "native-cursor.cfg"
    source.write_bytes(
        installation.NATIVE_CURSOR_HEADER + b"\n// tested presentation\n"
    )
    return source


def test_native_cursor_discovers_generic_engine_and_preserves_preferences_and_profiles(
    tmp_path: Path,
) -> None:
    native_click = runtime(tmp_path)
    native_click.parent.mkdir(parents=True)
    native_click.write_bytes(b"// existing native click preferences remain unchanged\n")
    unrelated = native_click.parent / "unrelated.js"
    unrelated.write_bytes(b'pref("unrelated", true);\n')
    profile = tmp_path / "home/desktop/.mozilla/arbitrary-profile/prefs.js"
    profile.parent.mkdir(parents=True)
    profile.write_bytes(b'user_pref("unchanged", true);\n')
    source = cursor_source(tmp_path)
    backup = tmp_path / "cursor-backup.json"
    installation.configure_native_cursor(tmp_path, source, backup)
    directory = tmp_path / "usr/lib/future-browser"
    cfg = directory / "dotfiles-mouse.cfg"
    bootstrap = directory / "defaults/pref/zz-dotfiles-mouse-cursor.js"
    assert cfg.read_bytes() == source.read_bytes()
    assert bootstrap.read_bytes() == installation.NATIVE_CURSOR_BOOTSTRAP
    assert (
        b'pref("general.config.filename", "dotfiles-mouse.cfg");'
        in bootstrap.read_bytes()
    )
    assert b'pref("general.config.obscure_value", 0);' in bootstrap.read_bytes()
    assert b'pref("general.config.sandbox_enabled", false);' in bootstrap.read_bytes()
    assert (
        native_click.read_bytes()
        == b"// existing native click preferences remain unchanged\n"
    )
    assert unrelated.read_bytes() == b'pref("unrelated", true);\n'
    assert profile.read_bytes() == b'user_pref("unchanged", true);\n'
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o644
    before = cfg.stat().st_mtime_ns, bootstrap.stat().st_mtime_ns, backup.read_bytes()
    installation.configure_native_cursor(tmp_path, source, backup)
    assert before == (
        cfg.stat().st_mtime_ns,
        bootstrap.stat().st_mtime_ns,
        backup.read_bytes(),
    )
    installation.restore(tmp_path, backup)
    assert not cfg.exists()
    assert not bootstrap.exists()
    assert profile.read_bytes() == b'user_pref("unchanged", true);\n'


@pytest.mark.parametrize(
    "conflict",
    [
        "dotfiles-mouse.cfg",
        "defaults/pref/zz-dotfiles-mouse-cursor.js",
    ],
)
def test_native_cursor_target_conflict_is_detected_before_any_engine_write(
    tmp_path: Path,
    conflict: str,
) -> None:
    runtime(tmp_path, "a-browser")
    runtime(tmp_path, "z-browser")
    path = tmp_path / "usr/lib/z-browser" / conflict
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"// unrelated configuration\n")
    backup = tmp_path / "cursor-backup.json"
    with pytest.raises(FileExistsError, match="Unrelated"):
        installation.configure_native_cursor(tmp_path, cursor_source(tmp_path), backup)
    assert not (tmp_path / "usr/lib/a-browser/dotfiles-mouse.cfg").exists()
    assert not backup.exists()
    assert path.read_bytes() == b"// unrelated configuration\n"


@pytest.mark.parametrize("directory", ["defaults/pref", "browser/defaults/preferences"])
@pytest.mark.parametrize(
    "definition",
    [
        'pref("general.config.filename", "other.cfg");',
        "pref('general.config.filename', 'other.cfg');",
        'lockPref("general.config.filename", "other.cfg");',
        'sticky_pref("general.config.filename", "other.cfg");',
        'pref("general.config.filename", otherFilename);',
        'pref("general.config.obscure_value", 13);',
        'pref("general.config.sandbox_enabled", true);',
    ],
)
def test_native_cursor_refuses_conflicting_autoconfig_before_mutation(
    tmp_path: Path,
    directory: str,
    definition: str,
) -> None:
    runtime(tmp_path, "a-browser")
    runtime(tmp_path, "z-browser")
    pref = tmp_path / "usr/lib/z-browser" / directory / "existing-autoconfig.js"
    pref.parent.mkdir(parents=True)
    pref.write_text(definition, encoding="utf-8")
    backup = tmp_path / "cursor-backup.json"
    with pytest.raises(FileExistsError, match="Conflicting AutoConfig"):
        installation.configure_native_cursor(tmp_path, cursor_source(tmp_path), backup)
    assert not backup.exists()
    assert not (tmp_path / "usr/lib/a-browser/dotfiles-mouse.cfg").exists()
    assert pref.read_text(encoding="utf-8") == definition


def test_native_cursor_accepts_matching_pref_and_ignores_commented_definitions(
    tmp_path: Path,
) -> None:
    runtime(tmp_path)
    pref = tmp_path / "usr/lib/future-browser/defaults/pref/preserved.js"
    pref.parent.mkdir(parents=True)
    contents = (
        '// pref("general.config.filename", "other.cfg");\n'
        '/* pref("general.config.filename", "other.cfg"); */\n'
        'pref("documentation.url", "https://example.test/path");\n'
        'pref("general.config.filename", "dotfiles-mouse.cfg");\n'
    )
    pref.write_text(contents, encoding="utf-8")
    installation.configure_native_cursor(
        tmp_path, cursor_source(tmp_path), tmp_path / "cursor-backup.json"
    )
    assert pref.read_text(encoding="utf-8") == contents


def test_native_cursor_restores_existing_owned_files_and_modes_exactly(
    tmp_path: Path,
) -> None:
    runtime(tmp_path)
    directory = tmp_path / "usr/lib/future-browser"
    cfg = directory / "dotfiles-mouse.cfg"
    bootstrap = directory / "defaults/pref/zz-dotfiles-mouse-cursor.js"
    bootstrap.parent.mkdir(parents=True)
    old = installation.NATIVE_CURSOR_HEADER + b"\n// previous\n"
    cfg.write_bytes(old)
    cfg.chmod(0o600)
    bootstrap.write_bytes(old)
    bootstrap.chmod(0o640)
    backup = tmp_path / "cursor-backup.json"
    installation.configure_native_cursor(tmp_path, cursor_source(tmp_path), backup)
    installation.restore(tmp_path, backup)
    assert cfg.read_bytes() == bootstrap.read_bytes() == old
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    assert stat.S_IMODE(bootstrap.stat().st_mode) == 0o640


def test_native_cursor_validation_is_read_only_and_rejects_symlinked_destinations(
    tmp_path: Path,
) -> None:
    runtime(tmp_path)
    source = cursor_source(tmp_path)
    installation.validate_native_cursor(tmp_path, source)
    assert not (tmp_path / "usr/lib/future-browser/defaults").exists()
    target = tmp_path / "usr/lib/future-browser/dotfiles-mouse.cfg"
    target.symlink_to(source)
    with pytest.raises(ValueError):
        installation.configure_native_cursor(tmp_path, source, tmp_path / "backup.json")
    assert target.is_symlink()
    assert not (tmp_path / "backup.json").exists()


def test_native_cursor_automatically_restores_all_files_after_failed_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime(tmp_path)
    source = cursor_source(tmp_path)
    target = (
        tmp_path / "usr/lib/future-browser/defaults/pref/zz-dotfiles-mouse-cursor.js"
    )
    backup = tmp_path / "cursor-backup.json"
    real_replace = Path.replace

    def fail_bootstrap(self: Path, destination: Path) -> Path:
        if destination == target:
            raise OSError("bootstrap write failed")
        return real_replace(self, destination)

    monkeypatch.setattr(Path, "replace", fail_bootstrap)
    with pytest.raises(OSError, match="bootstrap write failed"):
        installation.configure_native_cursor(tmp_path, source, backup)
    cfg = tmp_path / "usr/lib/future-browser/dotfiles-mouse.cfg"
    assert not cfg.exists()
    assert not target.exists()
    assert backup.exists()
    installation.restore(tmp_path, backup)
    assert not cfg.exists()
