#!/usr/bin/env python3
"""Build and run the disposable native bridge probes; never use a host display."""

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from enum import StrEnum
from pathlib import Path


class Backend(StrEnum):
    KWIN = "kwin"
    HYPRLAND = "hyprland"


PROTOCOLS = (
    (
        "fake-input",
        "https://raw.githubusercontent.com/KDE/plasma-wayland-protocols/"
        "1db07441870d54157e937674b99380a7dcc0fb32/src/protocols/fake-input.xml",
        "89f4ada4a1f09168a4528f47c0495e3f89dc2a25e8b23f4539ed3f5110eff708",
    ),
    (
        "xdg-shell",
        "https://gitlab.freedesktop.org/wayland/wayland-protocols/-/raw/"
        "3eab2dccf4bfdd85c16d312a6c8c8fbc2a6e73a8/stable/xdg-shell/xdg-shell.xml",
        "8cd3980d0783e1f55d12901ac51533204af71487cc4dc69ee00bb7096647d9de",
    ),
    (
        "virtual-pointer",
        "https://raw.githubusercontent.com/hyprwm/Hyprland/"
        "acc1aa0bfd4bd575dcb0f76c35ccf12b660a1ab9/protocols/"
        "wlr-virtual-pointer-unstable-v1.xml",
        "3ff6d540be0bc5228195bf072bde42117ea17945a5c2061add5d3cf97d6bb524",
    ),
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(command: list[str], log: Path, timeout: int = 120) -> None:
    with log.open("w") as output:
        subprocess.run(
            command,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=timeout,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=[*Backend, "both"], default="both")
    parser.add_argument("--kwin-bridge", required=True, type=Path)
    parser.add_argument("--hyprland-bridge", type=Path)
    parser.add_argument("--render-node", type=Path, required=True)
    parser.add_argument(
        "--artifacts",
        type=Path,
        help="New directory; retained logs and generated files",
    )
    parser.add_argument(
        "--protocol-dir", type=Path, help="Offline XML inputs; still hash checked"
    )
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    backends = list(Backend) if args.backend == "both" else [Backend(args.backend)]
    if Backend.HYPRLAND in backends and args.hyprland_bridge is None:
        parser.error("--hyprland-bridge is required for Hyprland")
    render = args.render_node.resolve(strict=True)
    device = render.stat()
    if (
        render.parent != Path("/dev/dri")
        or not render.name.startswith("renderD")
        or not stat.S_ISCHR(device.st_mode)
        or os.major(device.st_rdev) != 226
        or os.minor(device.st_rdev) < 128
    ):
        parser.error(
            "--render-node must be a DRM render node, never a card or input device"
        )
    for tool in (
        "bwrap",
        "cmake",
        "ninja",
        "g++",
        "wayland-scanner",
        "pkg-config",
        "dbus-run-session",
        "kwin_wayland",
        "kdotool",
    ):
        if shutil.which(tool) is None:
            parser.error(f"missing prerequisite: {tool}")
    if Backend.HYPRLAND in backends:
        for tool in ("Hyprland", "hyprctl"):
            if shutil.which(tool) is None:
                parser.error(f"missing prerequisite: {tool}")
    # Check dependency before entering the private filesystem.
    import dbus_fast  # noqa: F401

    if args.artifacts:
        root = args.artifacts.resolve()
        root.mkdir(parents=True, exist_ok=False)
    else:
        parent = here / "artifacts"
        parent.mkdir(exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="native-", dir=parent))
    root.chmod(0o700)
    print(f"Artifacts: {root}", flush=True)
    protocols = root / "protocols"
    protocols.mkdir()
    for name, url, expected in PROTOCOLS:
        destination = protocols / f"{name}.xml"
        if args.protocol_dir:
            shutil.copyfile(args.protocol_dir / destination.name, destination)
        else:
            with urllib.request.urlopen(url, timeout=30) as response:
                destination.write_bytes(response.read())
        if digest(destination) != expected:
            raise RuntimeError(f"protocol hash mismatch: {name}")
    (root / "protocol-origins.json").write_text(json.dumps(PROTOCOLS, indent=2) + "\n")
    build = root / "build"
    checked(
        [
            "cmake",
            "-S",
            str(here),
            "-B",
            str(build),
            "-G",
            "Ninja",
            f"-DPROTOCOL_DIR={protocols}",
        ],
        root / "configure.log",
    )
    checked(["cmake", "--build", str(build)], root / "build.log")
    for backend in backends:
        lab = root / backend
        lab.mkdir()
        for directory in ("home", "config", "cache", "data", "runtime"):
            (lab / directory).mkdir(mode=0o700)
        shutil.copyfile(build / "mouse-target-client", lab / "client")
        (lab / "client").chmod(0o700)
        bridge = args.kwin_bridge.resolve(strict=True)
        plugin_dir = lab / "plugins/kwin/effects/plugins"
        plugin_dir.mkdir(parents=True)
        shutil.copyfile(bridge, plugin_dir / "mousetarget.so")
        (lab / "config/kwinrc").write_text(
            "[Plugins]\nmousetargetEnabled="
            + ("true" if backend == Backend.KWIN else "false")
            + "\n"
        )
        if backend == Backend.HYPRLAND:
            hypr_bridge = args.hyprland_bridge.resolve(strict=True)
            shutil.copyfile(hypr_bridge, lab / "mouse_target_hyprland.so")
            (lab / "config/hyprland.lua").write_text(
                'hl.monitor({output="",mode="800x600@60",position="auto",scale=1})\n'
                "hl.config({animations={enabled=false},xwayland={enabled=false}})\n"
            )
        (lab / "artifacts.json").write_text(
            json.dumps(
                {
                    "backend": backend,
                    "kwin_bridge_sha256": digest(bridge),
                    "hyprland_bridge_sha256": digest(hypr_bridge)
                    if backend == Backend.HYPRLAND
                    else None,
                    "client_sha256": digest(lab / "client"),
                    "render_node": str(render),
                },
                indent=2,
            )
            + "\n"
        )
        command = [
            "bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib",
            "/lib64",
            "--ro-bind",
            "/etc",
            "/etc",
            "--ro-bind",
            "/sys",
            "/sys",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--dir",
            "/dev/dri",
            "--dev-bind",
            str(render),
            str(render),
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/tmp",
            "--bind",
            str(lab),
            "/lab",
            "--dir",
            "/harness",
            "--ro-bind",
            str(here / "probe.py"),
            "/harness/probe.py",
            "--chdir",
            "/lab",
            "--clearenv",
        ]
        # Preserve the selected Python environment, without exposing the user's home.
        for prefix in sorted({sys.prefix, sys.base_prefix}):
            if prefix != "/usr":
                command += ["--ro-bind", prefix, prefix]
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/lab/home",
            "USER": "native-probe",
            "XDG_CONFIG_HOME": "/lab/config",
            "XDG_CACHE_HOME": "/lab/cache",
            "XDG_DATA_HOME": "/lab/data",
            "XDG_RUNTIME_DIR": "/lab/runtime",
            "XDG_SESSION_TYPE": "wayland",
            "XDG_CURRENT_DESKTOP": "KDE",
            "WAYLAND_DISPLAY": "mmb-parent-wayland",
            "QT_PLUGIN_PATH": "/lab/plugins",
            "KWIN_COMPOSE": "O2",
            "LIBSEAT_BACKEND": "logind",
            "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/run/no-system-bus",
            "HYPRLAND_NO_SD_VARS": "1",
            "HYPRLAND_NO_SD_TARGET": "1",
        }
        for name, value in environment.items():
            command += ["--setenv", name, value]
        command += [
            "--",
            "/usr/bin/dbus-run-session",
            "--",
            sys.executable,
            "-B",
            "/harness/probe.py",
            backend,
            render.name,
        ]
        (lab / "launch.json").write_text(json.dumps(command, indent=2) + "\n")
        checked(command, lab / "runner.log", timeout=150)
        result = json.loads((lab / "result.json").read_text())
        if result.get("passed") is not True:
            raise RuntimeError(f"{backend} failed; inspect {lab / 'result.json'}")
        print(f"{backend}: passed", flush=True)


if __name__ == "__main__":
    main()
