"""Prepare exact upstream sources without changing the installed daemon."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

UPSTREAM = "https://github.com/gnhen/midscroll.git"


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
    args = parser.parse_args()
    prepared = prepare(args.module.resolve(), args.cache.resolve())
    if args.build_package:
        subprocess.run(
            ["makepkg", "--nodeps", "--clean", "--cleanbuild", "--noconfirm"],
            cwd=prepared / "packaging/arch",
            check=True,
        )
        packages = list((prepared / "packaging/arch").glob("midscroll-*.pkg.tar.zst"))
        if len(packages) != 1:
            raise ValueError("Expected exactly one midscroll package")
        inspect_package(packages[0])
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
        f"{purelib}/midscroll_routing/session.py",
        "etc/systemd/system/midscroll.service.d/native-default.conf",
    }
    with tarfile.open(package) as archive:
        names = {entry.name for entry in archive.getmembers()}
        if not required <= names:
            raise ValueError("Package lacks its system-interpreter routing dependency")
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
                    "runpy.run_path(sys.argv.pop(1), run_name='__main__')",
                    str(root / purelib),
                    str(root / "usr/bin/midscroll"),
                    "--native-default",
                    "--help",
                ],
                stdout=subprocess.DEVNULL,
                check=True,
            )


if __name__ == "__main__":
    main()
