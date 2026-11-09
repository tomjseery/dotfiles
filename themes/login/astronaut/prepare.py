#!/usr/bin/env python3
"""Prepare one upstream SDDM preset without touching system configuration."""
import configparser
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile


def read_config(path):
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    config.read(path)
    return config


def prepare(repository, component, destination):
    manifest = json.loads((component / "upstream.json").read_text())
    revision, preset = manifest["commit"], manifest["preset"]
    digest = hashlib.sha256((component / "overrides.conf").read_bytes()).hexdigest()[:8]
    name = f"dotfiles-astronaut-{revision[:12]}-{preset}-{digest}"
    theme = destination / name
    if theme.exists():
        return theme
    theme.mkdir(parents=True)
    try:
        archive = subprocess.check_output(["git", "-C", str(repository), "archive", revision])
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            stream.extractall(theme, filter="data")
        config = read_config(theme / "Themes" / (preset + ".conf"))
        overrides = read_config(component / "overrides.conf")
        for section in overrides.sections():
            if not config.has_section(section):
                config.add_section(section)
            for key, value in overrides[section].items():
                config[section][key] = value
        with (theme / "theme.conf").open("w") as stream:
            config.write(stream, space_around_delimiters=False)
        metadata = read_config(theme / "metadata.desktop")
        metadata["SddmGreeterTheme"]["ConfigFile"] = "theme.conf"
        metadata["SddmGreeterTheme"]["Theme-Id"] = name
        with (theme / "metadata.desktop").open("w") as stream:
            metadata.write(stream, space_around_delimiters=False)
        (theme / ".dotfiles-login.json").write_text(json.dumps({**manifest, "name": name}, indent=2) + "\n")
    except BaseException:
        import shutil
        shutil.rmtree(theme)
        raise
    return theme


if __name__ == "__main__":
    print(prepare(*(Path(value) for value in sys.argv[1:])))
