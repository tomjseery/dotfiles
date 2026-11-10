"""Render the current theme's existing directional arrows into native cursor CSS."""

import argparse
import base64
import binascii
import json
import os
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path

from midscroll_routing.installation import replace_file

MARKER = "/* DOTFILES_CURSOR_IMAGES */ {}"
NAMES = {
    "up": "up-arrow",
    "down": "down-arrow",
    "left": "left-arrow",
    "right": "right-arrow",
}


@dataclass(frozen=True)
class CursorImage:
    png: bytes
    x: int
    y: int


def read_cursor(path: Path, size: int) -> CursorImage:
    data = path.read_bytes()
    if len(data) < 16 or len(data) > 8_000_000:
        raise ValueError("Invalid cursor file size")
    magic, header, _version, count = struct.unpack_from("<4I", data)
    if (
        magic != 0x72756358
        or header < 16
        or count > 1024
        or header + count * 12 > len(data)
    ):
        raise ValueError("Invalid Xcursor header")
    entries = [
        struct.unpack_from("<3I", data, header + index * 12) for index in range(count)
    ]
    images = [
        (abs(nominal - size), offset)
        for kind, nominal, offset in entries
        if kind == 0xFFFD0002
    ]
    if not images:
        raise ValueError("Cursor contains no images")
    _, offset = min(images)
    if offset + 36 > len(data):
        raise ValueError("Truncated cursor image")
    length, kind, _nominal, _version, width, height, x, y, _delay = struct.unpack_from(
        "<9I", data, offset
    )
    if (
        kind != 0xFFFD0002
        or length < 36
        or not 0 < width <= 128
        or not 0 < height <= 128
        or x >= width
        or y >= height
    ):
        raise ValueError("Invalid cursor image geometry")
    start = offset + length
    if start + width * height * 4 > len(data):
        raise ValueError("Truncated cursor pixels")
    raw = data[start : start + width * height * 4]
    rgba = bytearray(len(raw))
    for index in range(0, len(raw), 4):
        alpha = raw[index + 3]
        # Xcursor stores premultiplied ARGB; PNG carries straight RGBA.
        red, green, blue = (
            min(255, (raw[index + offset] * 255 + alpha // 2) // alpha) if alpha else 0
            for offset in (2, 1, 0)
        )
        rgba[index : index + 4] = bytes((red, green, blue, alpha))
    rows = b"".join(
        b"\0" + rgba[row * width * 4 : (row + 1) * width * 4] for row in range(height)
    )

    def chunk(kind: bytes, value: bytes) -> bytes:
        return (
            struct.pack(">I", len(value))
            + kind
            + value
            + struct.pack(">I", binascii.crc32(kind + value))
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return CursorImage(png, x, y)


def theme_directory(theme: str | None = None) -> Path:
    name = theme or os.environ.get("XCURSOR_THEME")
    if not name and shutil.which("kreadconfig6"):
        name = subprocess.check_output(
            [
                "kreadconfig6",
                "--file",
                "kcminputrc",
                "--group",
                "Mouse",
                "--key",
                "cursorTheme",
            ],
            text=True,
        ).strip()
    roots = [
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / "icons",
        Path.home() / ".icons",
        Path("/usr/share/icons"),
    ]
    for candidate in [name, "breeze_cursors"]:
        if not candidate or "/" in candidate or candidate in {".", ".."}:
            continue
        for root in roots:
            directory = root / candidate / "cursors"
            if all((directory / value).is_file() for value in NAMES.values()):
                return directory
    raise FileNotFoundError("No theme supplies the existing directional arrow cursors")


def compile_config(template: Path, theme: str | None = None, size: int = 24) -> bytes:
    if not 1 <= size <= 128:
        raise ValueError("Cursor size must be between 1 and 128")
    source = template.read_text(encoding="utf-8")
    if source.count(MARKER) != 1:
        raise ValueError("Native cursor template marker is missing or ambiguous")
    directory = theme_directory(theme)
    images: dict[str, dict[str, str | int]] = {}
    for direction, filename in NAMES.items():
        image = read_cursor(directory / filename, size)
        images[direction] = {
            "url": "data:image/png;base64," + base64.b64encode(image.png).decode(),
            "x": image.x,
            "y": image.y,
        }
    return source.replace(MARKER, json.dumps(images, separators=(",", ":"))).encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--theme")
    parser.add_argument("--size", type=int, default=24)
    args = parser.parse_args()
    replace_file(
        args.output, compile_config(args.template, args.theme, args.size), 0o600
    )


if __name__ == "__main__":
    main()
