#!/usr/bin/env python3
"""Merge owned settings into live files without replacing unrelated preferences."""
import argparse
import json
import os
from pathlib import Path
import tempfile


def entries(text):
    group = ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            group = line
        elif "=" in line and not line.startswith(("#", ";")):
            key, value = line.split("=", 1)
            yield group, key, value


def merge_kconfig(original, overlay):
    lines = original.splitlines()
    for group, key, value in entries(overlay):
        start = next((i + 1 for i, line in enumerate(lines) if line == group), None)
        if start is None:
            lines.extend(["", group, f"{key}={value}"])
            continue
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
        existing = next((i for i in range(start, end) if lines[i].startswith(key + "=")), None)
        if existing is None:
            lines.insert(end, f"{key}={value}")
        else:
            lines[existing] = f"{key}={value}"
    return "\n".join(lines).lstrip("\n") + "\n"


def merge_json(original, overlay):
    def merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = value
        return target
    return json.dumps(merge(json.loads(original or "{}"), json.loads(overlay)), indent=4) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("layer", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--kind", choices=["kconfig", "json"])
    args = parser.parse_args()
    home = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    targets = {
        "kdeglobals": config / "kdeglobals",
        "kwinrc": config / "kwinrc",
        "konsolerc": home / ".var/app/org.kde.konsole/config/konsolerc",
        "code.json": config / "Code/User/settings.json",
        "vesktop.json": config / "vesktop/settings.json",
    }
    # Validate every merge before making any writes.
    changes = []
    for kind, merger in [("kconfig", merge_kconfig), ("json", merge_json)]:
        if args.kind and args.kind != kind:
            continue
        for source in sorted((args.layer / kind).glob("*")):
            target = targets[source.name]
            if target.is_symlink():
                raise SystemExit(f"Refusing to edit a symlink: {target}. Migrate it to a live file first.")
            original = target.read_text() if target.exists() else ""
            result = merger(original, source.read_text())
            if original != result:
                changes.append((target, result))
    for target, result in changes:
        print(f"{'Would merge' if args.dry_run else 'Merge'} {target}")
        if args.dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".dotfiles-", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(result)
            os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o600)
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


if __name__ == "__main__":
    main()
