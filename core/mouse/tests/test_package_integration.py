import subprocess
import tarfile
from pathlib import Path

import pytest

from midscroll_routing.source import inspect_package


def test_archive_rejects_venv_only_routing_dependency(tmp_path: Path) -> None:
    package = tmp_path / "bad.tar"
    with tarfile.open(package, "w") as archive:
        for name in [
            "usr/bin/midscroll",
            "usr/bin/midscroll-router",
            "home/developer/project/.venv/lib/python3.14/site-packages/midscroll_routing/__init__.py",
        ]:
            archive.addfile(tarfile.TarInfo(name))
    with pytest.raises(ValueError, match="system-interpreter"):
        inspect_package(package)


def test_archive_rejects_unrelated_home_files(tmp_path: Path) -> None:
    purelib = (
        subprocess.check_output(
            [
                "/usr/bin/python3",
                "-I",
                "-S",
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            text=True,
        )
        .strip()
        .lstrip("/")
    )
    package = tmp_path / "bad.tar"
    with tarfile.open(package, "w") as archive:
        for name in [
            "usr/bin/midscroll",
            "usr/bin/midscroll-router",
            f"{purelib}/midscroll_routing/__init__.py",
            f"{purelib}/midscroll_routing/routing.py",
            f"{purelib}/midscroll_routing/session.py",
            "usr/share/midscroll/native-default.conf",
            "usr/bin/midscroll-overlay-session",
            "usr/bin/midscroll-session-start",
            "home/developer/unrelated",
        ]:
            entry = tarfile.TarInfo(name)
            entry.mode = 0o755 if name.startswith("usr/bin/") else 0o644
            archive.addfile(entry)
    with pytest.raises(ValueError, match="unexpected installation"):
        inspect_package(package)
