#!/usr/bin/env python3
"""Merge the repository's input-remapper policy into the live config."""

import json
import os
import pathlib
import sys
import tempfile


def read_json(path: pathlib.Path) -> dict:
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)

    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} DESIRED_CONFIG LIVE_CONFIG")

    desired_path = pathlib.Path(sys.argv[1])
    live_path = pathlib.Path(sys.argv[2])
    desired = read_json(desired_path)
    live = read_json(live_path)

    # Preserve unrelated input-remapper settings, but make the repository's
    # autoload policy authoritative. In particular this removes the obsolete
    # disable-middle entries for both physical mice.
    live["autoload"] = desired["autoload"]
    live.setdefault("version", desired["version"])

    rendered = json.dumps(live, indent=4, ensure_ascii=False) + "\n"
    if live_path.exists() and live_path.read_text(encoding="utf-8") == rendered:
        return

    live_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=live_path.parent, prefix=f".{live_path.name}.", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(rendered)
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, live_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


if __name__ == "__main__":
    main()
