"""Prepare exact upstream sources without changing the installed daemon."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from midscroll_routing.installation import replace_file

UPSTREAM = "https://github.com/gnhen/midscroll.git"
BASELINE = "ac76b554cf6b279d646dee8336b45390d9db3597"


def prepare(module: Path, cache: Path) -> Path:
    revision = (module / "upstream-revision").read_text(encoding="utf-8").strip()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("An immutable upstream revision is required")
    patch = module / "patches/native-routing.patch"
    digest = hashlib.sha256(revision.encode() + patch.read_bytes())
    package = module / "src/midscroll_routing"
    for file in sorted(package.glob("*.py")):
        digest.update(file.name.encode() + file.read_bytes())
    for file in sorted((module / "package").rglob("*")):
        if file.is_file():
            digest.update(str(file.relative_to(module)).encode() + file.read_bytes())
            digest.update(str(file.stat().st_mode & 0o777).encode())
    identity = digest.hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / identity
    if destination.exists():
        manifest_path = destination / ".dotfiles-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not manifest:
            raise ValueError("Invalid prepared-source manifest")
        for name, expected in manifest.items():
            path = destination / name
            if (
                not path.resolve().is_relative_to(destination.resolve())
                or path.is_symlink()
            ):
                raise ValueError("Invalid prepared-source path")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"Prepared source changed: {name}")
        return destination
    repository = cache / "upstream.git"
    if not repository.exists():
        subprocess.run(
            ["git", "clone", "--bare", UPSTREAM, str(repository)], check=True
        )
    subprocess.run(
        ["git", "--git-dir", str(repository), "fetch", "origin", revision], check=True
    )
    with tempfile.TemporaryDirectory(dir=cache, prefix="prepare-") as temporary:
        staging = Path(temporary)
        archive = staging / "upstream.tar"
        with archive.open("wb") as output:
            subprocess.run(
                ["git", "--git-dir", str(repository), "archive", revision],
                stdout=output,
                check=True,
            )
        source = staging / "source"
        source.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(source, filter="data")
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=source, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=source, check=True)
        shutil.copytree(
            package,
            source / "midscroll_routing",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(module / "package", source / "dotfiles")
        # The Arch package is the runtime dependency owner for this module.
        build = source / "packaging/arch/PKGBUILD"
        text = build.read_text(encoding="utf-8")
        text = text.replace("pkgver=1.15", "pkgver=1.15.r20.g077d1b3")
        text = text.replace(
            "depends=('python' ", "depends=('python>=3.14' 'python-dbus-fast>=5.2' "
        )
        text = text.replace(
            '    install -Dm755 midscroll.py "$pkgdir/usr/bin/midscroll"',
            "    local site_packages\n"
            '    site_packages=$(/usr/bin/python3 -I -S -c "import sysconfig; '
            "print(sysconfig.get_path('purelib'))\")\n"
            '    install -d "$pkgdir$site_packages"\n'
            '    cp -r midscroll_routing "$pkgdir$site_packages/"\n'
            '    install -Dm755 midscroll.py "$pkgdir/usr/bin/midscroll"',
        )
        text = text.replace(
            '    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/midscroll/LICENSE"',
            '    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/midscroll/LICENSE"'
            '\n    cp -r dotfiles/. "$pkgdir/"\n    chown -R root:root "$pkgdir"',
        )
        build.write_text(text, encoding="utf-8")
        (source / ".dotfiles-source").write_text(revision + "\n", encoding="utf-8")
        manifest = {
            str(file.relative_to(source)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in source.rglob("*")
            if file.is_file()
        }
        (source / ".dotfiles-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True), encoding="utf-8"
        )
        source.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--build-package", action="store_true")
    parser.add_argument("--prepare-recovery", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.prepare_recovery:
        recovery = prepare_recovery(args.cache.resolve())
        if args.manifest is not None:
            replace_file(
                args.manifest,
                json.dumps(
                    {
                        "package": str(recovery),
                        "sha256": hashlib.sha256(recovery.read_bytes()).hexdigest(),
                    }
                ).encode(),
                0o600,
            )
        print(recovery)
        return
    prepared = prepare(args.module.resolve(), args.cache.resolve())
    if args.build_package:
        subprocess.run(
            [
                "makepkg",
                "--force",
                "--nodeps",
                "--clean",
                "--cleanbuild",
                "--noconfirm",
            ],
            cwd=prepared / "packaging/arch",
            check=True,
        )
        packages = list((prepared / "packaging/arch").glob("midscroll-*.pkg.tar.zst"))
        if len(packages) != 1:
            raise ValueError("Expected exactly one midscroll package")
        inspect_package(packages[0])
        if args.manifest is not None:
            replace_file(
                args.manifest,
                json.dumps(
                    {
                        "package": str(packages[0]),
                        "sha256": hashlib.sha256(packages[0].read_bytes()).hexdigest(),
                    }
                ).encode(),
                0o600,
            )
    print(prepared)


def inspect_package(package: Path) -> None:
    """Reject developer paths and prove imports from the packaged artifact."""
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
    required = {
        "usr/bin/midscroll",
        "usr/bin/midscroll-router",
        f"{purelib}/midscroll_routing/__init__.py",
        f"{purelib}/midscroll_routing/routing.py",
        f"{purelib}/midscroll_routing/session.py",
        "usr/share/midscroll/native-default.conf",
        "usr/bin/midscroll-overlay-session",
        "usr/bin/midscroll-session-start",
    }
    with tarfile.open(package) as archive:
        names = {entry.name for entry in archive.getmembers()}
        if not required <= names:
            raise ValueError("Package lacks its system-interpreter routing dependency")
        for name in required:
            entry = archive.getmember(name)
            if not entry.isfile() or (
                name.startswith("usr/bin/") and not entry.mode & 0o111
            ):
                raise ValueError(f"Invalid packaged runtime file or mode: {name}")
        if any(
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or (not name.startswith(".") and Path(name).parts[0] not in {"etc", "usr"})
            for name in names
        ):
            raise ValueError("Package contains an unexpected installation path")
        with tempfile.TemporaryDirectory(
            prefix="midscroll-package-check-"
        ) as temporary:
            root = Path(temporary)
            archive.extractall(root, filter="data")
            subprocess.run(
                [
                    "/usr/bin/python3",
                    "-I",
                    "-c",
                    "import runpy, sys; sys.path.insert(0, sys.argv.pop(1)); "
                    "import midscroll_routing.session; "
                    "runpy.run_path(sys.argv.pop(1), run_name='__main__')",
                    str(root / purelib),
                    str(root / "usr/bin/midscroll"),
                    "--native-default",
                    "--help",
                ],
                stdout=subprocess.DEVNULL,
                check=True,
            )


def prepare_recovery(cache: Path) -> Path:
    """Rebuild and verify the exact installed executable baseline, without root."""
    installed = subprocess.check_output(
        ["pacman", "-Q", "midscroll"], text=True
    ).strip()
    recorded = Path("/var/lib/dotfiles-mouse/current-package.pkg.tar.zst")
    if installed != "midscroll 1.15-1" and recorded.is_file():
        status = recorded.stat()
        if status.st_uid != 0 or status.st_mode & 0o022:
            raise ValueError("Recorded recovery package is not root-owned")
        version = subprocess.check_output(
            ["pacman", "-Qp", str(recorded)], text=True
        ).strip()
        if version != installed:
            raise ValueError("Recorded package differs from the installed version")
        return recorded
    if installed != "midscroll 1.15-1":
        raise ValueError(
            "Reassess recovery for the currently installed midscroll version"
        )
    repository = cache / "upstream.git"
    if not repository.is_dir():
        raise ValueError("Prepare candidate source before preparing recovery")
    binaries = [
        "midscroll",
        "midscroll-overlay",
        "midscroll-settings",
        "midscroll-apply",
    ]
    originals: dict[str, bytes] = {}
    for binary in binaries:
        expected = subprocess.check_output(
            ["git", "--git-dir", str(repository), "show", f"{BASELINE}:{binary}.py"]
        )
        if Path(f"/usr/bin/{binary}").read_bytes() != expected:
            raise ValueError(
                f"Installed {binary} differs from the verified recovery source"
            )
        originals[binary] = expected
    destination = cache / f"recovery-{BASELINE}"
    archive_path = destination / "packaging/arch/midscroll-1.15-1-any.pkg.tar.zst"
    if not destination.exists():
        with tempfile.TemporaryDirectory(dir=cache, prefix="recovery-") as temporary:
            staging = Path(temporary)
            archive = staging / "source.tar"
            with archive.open("wb") as output:
                subprocess.run(
                    ["git", "--git-dir", str(repository), "archive", BASELINE],
                    stdout=output,
                    check=True,
                )
            source = staging / "source"
            source.mkdir()
            with tarfile.open(archive) as bundle:
                bundle.extractall(source, filter="data")
            build = source / "packaging/arch/PKGBUILD"
            text = build.read_text(encoding="utf-8").replace(
                "pkgver=1.14", "pkgver=1.15"
            )
            build.write_text(text, encoding="utf-8")
            subprocess.run(
                ["makepkg", "--nodeps", "--clean", "--cleanbuild", "--noconfirm"],
                cwd=source / "packaging/arch",
                check=True,
            )
            source.rename(destination)
    with tarfile.open(archive_path) as recovery_archive:
        for entry in recovery_archive.getmembers():
            if entry.isfile() and entry.name.startswith("usr/"):
                installed_file = Path("/") / entry.name
                member = recovery_archive.extractfile(entry)
                if member is None:
                    raise ValueError(f"Recovery file missing: {entry.name}")
                with member:
                    if (
                        not installed_file.is_file()
                        or installed_file.read_bytes() != member.read()
                        or installed_file.stat().st_mode & 0o777 != entry.mode & 0o777
                    ):
                        raise ValueError(
                            f"Installed package file differs: {entry.name}"
                        )
        for binary, expected in originals.items():
            member = recovery_archive.extractfile(f"usr/bin/{binary}")
            if member is None or member.read() != expected:
                raise ValueError(f"Recovery package does not restore {binary}")
    return archive_path


if __name__ == "__main__":
    main()
