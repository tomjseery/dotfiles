#!/usr/bin/env python3
"""Find and repair launcher identities that can split pinned tasks in Plasma."""

import argparse
import os
import re
import stat
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


def data_paths():
    user = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    if not user.is_absolute():
        user = Path.home() / ".local/share"
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [user, *(Path(path) for path in system.split(":") if path.startswith("/"))]


def desktop_entry(content):
    """Return values from the main group, leaving localized keys and actions alone."""
    active = False
    for line in content.splitlines():
        if line.startswith("["):
            active = line == "[Desktop Entry]"
        elif active and not line.startswith("#") and "=" in line:
            yield tuple(line.split("=", 1))


def installed_launchers(roots):
    launchers = {}
    for root in roots:
        directory = root / "applications"
        for path in sorted(directory.rglob("*.desktop")):
            if path.is_file():
                desktop_id = str(path.relative_to(directory)).replace("/", "-")
                launchers.setdefault(desktop_id, path)
    return {
        desktop_id: (path, values)
        for desktop_id, path in launchers.items()
        if (values := dict(desktop_entry(path.read_text(encoding="utf-8")))).get("Type")
        == "Application"
        and values.get("Hidden") != "true"
    }


def collisions(launchers):
    identities = defaultdict(set)
    for desktop_id, (_, values) in launchers.items():
        identities[desktop_id.removesuffix(".desktop").casefold()].add(desktop_id)
        window_class = values.get("StartupWMClass")
        if window_class:
            identities[window_class.casefold()].add(desktop_id)

    return {identity: sorted(ids) for identity, ids in sorted(identities.items()) if len(ids) > 1}


def change_window_class(content, window_class):
    entry = re.search(r"(?m)^\[Desktop Entry\]\r?\n", content)
    if entry is None:
        raise ValueError("Missing [Desktop Entry] group.")
    start = entry.end()
    next_group = re.search(r"(?m)^\[", content[start:])
    end = start + next_group.start() if next_group else len(content)
    body = content[start:end]
    line_break = "\r\n" if content[start - 2:start] == "\r\n" else "\n"
    replacement = f"StartupWMClass={window_class}{line_break}" if window_class else ""
    pattern = r"(?m)^StartupWMClass=[^\r\n]*(?:\r?\n|$)"
    updated, count = re.subn(pattern, lambda _: replacement, body)
    if count > 1:
        raise ValueError("Multiple StartupWMClass keys in [Desktop Entry].")
    if not count:
        updated = replacement + body
    return content[:start] + updated + content[end:]


def repair(user_data, launchers, desktop_id, window_class):
    if desktop_id not in launchers:
        raise ValueError(f"Launcher not found: {desktop_id}")
    if window_class is not None and (
        not window_class.strip() or any(char in window_class for char in "\r\n\0")
    ):
        raise ValueError("Supply the actual app ID or window class on a single line.")

    source, values = launchers[desktop_id]
    if window_class and values.get("StartupWMClass", "").casefold() != window_class.casefold():
        proposed = {**launchers, desktop_id: (source, {**values, "StartupWMClass": window_class})}
        conflicts = set(collisions(proposed).get(window_class.casefold(), ())) - {desktop_id}
        if conflicts:
            raise ValueError(f"{window_class} is also claimed by {', '.join(sorted(conflicts))}.")

    directory = user_data / "applications"
    target = source if source.is_relative_to(directory) else directory / desktop_id
    if (
        target.is_symlink()
        or not target.parent.resolve().is_relative_to(directory.resolve())
        or (target != source and target.exists())
    ):
        raise ValueError(f"Refusing to replace existing override: {target}")

    original = source.read_bytes().decode("utf-8")
    updated = change_window_class(original, window_class)
    if updated == original:
        return

    directory.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=".dotfiles-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(updated.encode("utf-8"))
        temporary.chmod(stat.S_IMODE(source.stat().st_mode) & 0o777)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Updated {target}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--set-class", nargs=2, metavar=("DESKTOP_ID", "WINDOW_CLASS"),
        help="set StartupWMClass from an observed window identity",
    )
    actions.add_argument(
        "--clear-class", metavar="DESKTOP_ID",
        help="remove an incorrect StartupWMClass claim",
    )
    args = parser.parse_args()
    roots = data_paths()
    try:
        launchers = installed_launchers(roots)
        change = args.set_class or (args.clear_class, None)
        if change[0]:
            repair(roots[0], launchers, *change)
            if "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":"):
                subprocess.run(["kbuildsycoca6", "--noincremental"], check=True)
        else:
            for identity, owners in collisions(launchers).items():
                print(f"{identity}: {', '.join(owners)}")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
