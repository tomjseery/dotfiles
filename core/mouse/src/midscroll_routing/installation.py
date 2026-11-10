"""Mouse-owned configuration staging and exact file recovery."""

import argparse
import base64
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

NATIVE_PREFS_HEADER = b"// Managed by dotfiles/core/mouse:"
NATIVE_PREFS = (
    NATIVE_PREFS_HEADER + b" native Gecko middle-click behaviour.\n"
    b'pref("general.autoScroll", true);\n'
    b'pref("middlemouse.paste", false);\n'
    b'pref("middlemouse.contentLoadURL", false);\n'
)
NATIVE_CURSOR_HEADER = (
    b"// Managed by dotfiles/core/mouse: native autoscroll cursor presentation."
)
NATIVE_CURSOR_BOOTSTRAP = (
    NATIVE_CURSOR_HEADER + b"\n"
    b'pref("general.config.filename", "dotfiles-mouse.cfg");\n'
    b'pref("general.config.obscure_value", 0);\n'
    b'pref("general.config.sandbox_enabled", false);\n'
)
AUTOCONFIG_VALUES = {
    "general.config.filename": {'"dotfiles-mouse.cfg"', "'dotfiles-mouse.cfg'"},
    "general.config.obscure_value": {"0"},
    "general.config.sandbox_enabled": {"false"},
}
JS_COMMENTS = re.compile(
    r""""(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|(?P<comment>//[^\r\n]*|/\*.*?\*/)""",
    re.DOTALL,
)
AUTOCONFIG_SETTING = re.compile(
    r"""\b(?:pref|sticky_pref|user_pref|defaultPref|lockPref)\s*\(\s*(["'])"""
    r"""(?P<key>general\.config\.(?:filename|obscure_value|sandbox_enabled))\1"""
    r"""\s*,\s*(?P<value>.*?)\)""",
    re.DOTALL,
)


def _validate_path(path: Path) -> None:
    """Reject links, special files and non-directory ancestors before mutation."""
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise ValueError(f"Refusing a configuration symlink: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Configuration is not a regular file: {path}")
    if any(parent.exists() and not parent.is_dir() for parent in path.parents):
        raise ValueError(f"Configuration parent is not a directory: {path}")


@dataclass(frozen=True, slots=True)
class FileState:
    data: bytes
    mode: int

    def __post_init__(self) -> None:
        if type(self.mode) is not int or not 0 <= self.mode <= 0o7777:
            raise ValueError("Invalid recovery permissions")


def replace_file(path: Path, data: bytes, mode: int = 0o644) -> None:
    _validate_path(path)
    FileState(data, mode)
    if (
        path.exists()
        and path.read_bytes() == data
        and stat.S_IMODE(path.stat().st_mode) == mode
    ):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            os.fchmod(output.fileno(), mode)
            output.flush()
            os.fsync(output.fileno())
        _validate_path(path)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def merge_policy(existing: str, profile: str) -> str:
    owned = {"NATIVE_DEFAULT", "FALLBACK_APPS"}
    policy: dict[str, str] = {}
    for line in profile.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() in owned:
            if key.strip() in policy:
                raise ValueError("Duplicate owned policy key in installation profile")
            policy[key.strip()] = value.partition("#")[0].strip()
    if set(policy) != owned or policy["NATIVE_DEFAULT"] != "true":
        raise ValueError("Invalid native-default installation profile")
    apps = policy["FALLBACK_APPS"]
    if apps and any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", app.strip()) for app in apps.split(",")
    ):
        raise ValueError("Invalid fallback application in installation profile")
    lines = [
        line
        for line in existing.splitlines(keepends=True)
        if not ("=" in line and line.partition("=")[0].strip() in owned)
    ]
    retained = "".join(lines)
    if retained and not retained.endswith(("\n", "\r")):
        retained += "\n"
    return retained + "".join(f"{key} = {policy[key]}\n" for key in sorted(owned))


def configure_system(root: Path, previous: Path | None) -> None:
    profile = safe_path(root, "usr/share/midscroll/native-default.conf").read_text(
        encoding="utf-8"
    )
    if previous is not None:
        _validate_path(previous)
    existing = profile if previous is None else previous.read_text(encoding="utf-8")
    destination = safe_path(root, "etc/midscroll.conf")
    mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
    replace_file(destination, merge_policy(existing, profile).encode(), mode)


def snapshot(root: Path, paths: list[str], destination: Path) -> None:
    saved: dict[str, dict[str, str | int] | None] = {}
    recorded: set[Path] = set()
    _validate_path(destination)
    for relative in paths:
        path = safe_path(root, relative)
        if path in recorded:
            raise ValueError("Duplicate recovery path")
        if _overlap(path, destination):
            raise ValueError("Recovery snapshot overlaps an owned path")
        recorded.add(path)
        if path.exists():
            saved[relative] = {
                "data": base64.b64encode(path.read_bytes()).decode(),
                "mode": stat.S_IMODE(path.stat().st_mode),
            }
        else:
            saved[relative] = None
    if destination.exists():
        raise FileExistsError(f"Recovery snapshot already exists: {destination}")
    replace_file(destination, json.dumps(saved, sort_keys=True).encode(), 0o600)


def safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or path.is_symlink()
        or not path.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError(f"Unsafe owned configuration path: {relative}")
    if not relative or Path(relative) == Path():
        raise ValueError("A configuration file path is required")
    _validate_path(path)
    return path


def _overlap(first: Path, second: Path) -> bool:
    first, second = first.resolve(), second.resolve()
    return first == second or first in second.parents or second in first.parents


def restore(root: Path, source: Path) -> None:
    _validate_path(source)
    saved = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(saved, dict):
        raise ValueError("Invalid recovery snapshot")
    validated: dict[Path, FileState | None] = {}
    for relative, entry in saved.items():
        path = safe_path(root, relative)
        if path in validated or _overlap(path, source):
            raise ValueError("Duplicate recovery path or snapshot overlap")
        if entry is not None:
            if not isinstance(entry, dict) or set(entry) != {"data", "mode"}:
                raise ValueError("Invalid recovery file")
            if not isinstance(entry["data"], str):
                raise ValueError("Invalid recovery data")
            validated[path] = FileState(
                base64.b64decode(entry["data"], validate=True), entry["mode"]
            )
        else:
            validated[path] = None
    # Parent/child destinations cannot both describe regular files.
    if any(parent in validated for path in validated for parent in path.parents):
        raise ValueError("Overlapping recovery paths")
    for path, entry in validated.items():
        if entry is None:
            path.unlink(missing_ok=True)
        else:
            replace_file(path, entry.data, entry.mode)


def _gecko_runtimes(root: Path) -> list[Path]:
    library = root / "usr/lib"
    _validate_path(library / ".mouse-path-validation")
    runtimes: list[Path] = []
    if library.exists():
        for runtime in sorted(library.iterdir()):
            markers = (
                runtime / "libxul.so",
                runtime / "application.ini",
                runtime / "browser/omni.ja",
            )
            if not all(marker.is_file() for marker in markers):
                continue
            for marker in markers:
                safe_path(root, str(marker.relative_to(root)))
            runtimes.append(runtime)
    return runtimes


def _native_default_paths(root: Path) -> list[str]:
    paths: list[str] = []
    for runtime in _gecko_runtimes(root):
        # GRE defaults/pref loads before browser omni.ja defaults. The
        # application defaults/preferences directory loads afterward.
        # Mozilla Preferences.cpp and nsXREDirProvider::GetFiles own this order.
        relative = str(
            (runtime / "browser/defaults/preferences/zz-dotfiles-mouse.js").relative_to(
                root
            )
        )
        path = safe_path(root, relative)
        if path.exists():
            existing = path.read_bytes()
            if existing.strip() and not existing.startswith(NATIVE_PREFS_HEADER):
                raise FileExistsError(f"Unrelated Gecko preference file: {path}")
        paths.append(relative)
    return paths


def validate_native_defaults(root: Path) -> None:
    """Preflight all discovered application defaults without creating files."""
    _native_default_paths(root)


def configure_native_defaults(root: Path, backup: Path) -> None:
    """Apply application defaults, leaving user profiles and other prefs alone."""
    paths = _native_default_paths(root)
    if all(
        (path := safe_path(root, relative)).exists()
        and path.read_bytes() == NATIVE_PREFS
        and stat.S_IMODE(path.stat().st_mode) == 0o644
        for relative in paths
    ):
        return
    snapshot(root, paths, backup)
    for relative in paths:
        replace_file(safe_path(root, relative), NATIVE_PREFS)


@dataclass(frozen=True, slots=True)
class ConfigurationFile:
    relative_path: str
    data: bytes


def _validate_autoconfig(root: Path, runtime: Path, bootstrap: Path) -> None:
    for directory in (
        runtime / "defaults/pref",
        runtime / "browser/defaults/preferences",
    ):
        _validate_path(directory / ".mouse-path-validation")
        for preference in sorted(directory.glob("*.js")):
            path = safe_path(root, str(preference.relative_to(root)))
            if path == bootstrap:
                continue
            text = JS_COMMENTS.sub(
                lambda match: "" if match.group("comment") else match.group(),
                path.read_text(encoding="utf-8"),
            )
            for setting in AUTOCONFIG_SETTING.finditer(text):
                if (
                    setting.group("value").strip()
                    not in AUTOCONFIG_VALUES[setting.group("key")]
                ):
                    raise FileExistsError(f"Conflicting AutoConfig preference: {path}")


def _native_cursor_files(root: Path, source: Path) -> list[ConfigurationFile]:
    _validate_path(source)
    data = source.read_bytes()
    if not data.startswith(NATIVE_CURSOR_HEADER + b"\n"):
        raise ValueError("Native cursor source is not the owned AutoConfig file")
    files: list[ConfigurationFile] = []
    for runtime in _gecko_runtimes(root):
        configuration = safe_path(
            root, str((runtime / "dotfiles-mouse.cfg").relative_to(root))
        )
        bootstrap = safe_path(
            root,
            str(
                (runtime / "defaults/pref/zz-dotfiles-mouse-cursor.js").relative_to(
                    root
                )
            ),
        )
        for path, contents in (
            (configuration, data),
            (bootstrap, NATIVE_CURSOR_BOOTSTRAP),
        ):
            if path.exists():
                existing = path.read_bytes()
                if existing.strip() and not existing.startswith(
                    NATIVE_CURSOR_HEADER + b"\n"
                ):
                    raise FileExistsError(
                        f"Unrelated native cursor configuration: {path}"
                    )
            files.append(ConfigurationFile(str(path.relative_to(root)), contents))
        _validate_autoconfig(root, runtime, bootstrap)
    return files


def validate_native_cursor(root: Path, source: Path) -> None:
    """Validate all native cursor destinations without changing browser files."""
    _native_cursor_files(root, source)


def configure_native_cursor(root: Path, source: Path, backup: Path) -> None:
    """Install the owned browser-chrome cursor presentation without profile edits."""
    files = _native_cursor_files(root, source)
    if all(
        (path := safe_path(root, file.relative_path)).exists()
        and path.read_bytes() == file.data
        and stat.S_IMODE(path.stat().st_mode) == 0o644
        for file in files
    ):
        return
    snapshot(root, [file.relative_path for file in files], backup)
    try:
        for file in files:
            replace_file(safe_path(root, file.relative_path), file.data)
    except OSError, ValueError:
        restore(root, backup)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    operations = parser.add_subparsers(dest="operation", required=True)
    config = operations.add_parser("configure-system")
    config.add_argument("--previous", type=Path)
    save = operations.add_parser("snapshot")
    save.add_argument("destination", type=Path)
    save.add_argument("paths", nargs="+")
    recover = operations.add_parser("restore")
    recover.add_argument("source", type=Path)
    defaults = operations.add_parser("native-defaults")
    defaults.add_argument("--backup", type=Path, required=True)
    defaults.add_argument("--dry-run", action="store_true")
    cursor = operations.add_parser("native-cursor")
    cursor.add_argument("--source", type=Path, required=True)
    cursor.add_argument("--backup", type=Path, required=True)
    cursor.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.root.resolve() == Path("/") and os.geteuid() != 0:
        parser.error("System configuration requires administrator authentication")
    if args.operation == "configure-system":
        configure_system(args.root, args.previous)
    elif args.operation == "snapshot":
        snapshot(args.root, args.paths, args.destination)
    elif args.operation == "native-defaults":
        if args.dry_run:
            validate_native_defaults(args.root)
            _validate_path(args.backup)
        else:
            configure_native_defaults(args.root, args.backup)
    elif args.operation == "native-cursor":
        if args.dry_run:
            validate_native_cursor(args.root, args.source)
            _validate_path(args.backup)
        else:
            configure_native_cursor(args.root, args.source, args.backup)
    else:
        restore(args.root, args.source)


if __name__ == "__main__":
    main()
