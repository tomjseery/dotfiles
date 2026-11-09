"""Read native compositor recipient snapshots and answer daemon requests."""

import asyncio
import json
import logging
import os
import stat
from pathlib import Path

from midscroll_routing import Target

log = logging.getLogger(__name__)
SOCKET = Path("/run/midscroll/state.sock")


async def target(desktop: str) -> Target | None:
    desktops = desktop.casefold().split(":")
    if "kde" in desktops:
        command = [
            "busctl",
            "--user",
            "--json=short",
            "call",
            "org.tomjseery.MouseTarget",
            "/MouseTarget",
            "org.tomjseery.MouseTarget",
            "target",
        ]
    elif "hyprland" in desktops:
        command = ["hyprctl", "-j", "mouse-target"]
    else:
        return None
    try:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 0.15)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        if process.returncode:
            log.debug(
                "Recipient bridge unavailable: %s",
                stderr.decode(errors="replace")[:256],
            )
            return None
        if len(stdout) > 4096:
            raise ValueError("Oversized recipient snapshot")
        payload = json.loads(stdout)
        if "kde" in desktops:
            if not isinstance(payload, dict) or payload.get("type") != "s":
                raise ValueError("Invalid D-Bus response type")
            data = payload.get("data")
            if (
                not isinstance(data, list)
                or len(data) != 1
                or not isinstance(data[0], str)
            ):
                raise ValueError("Invalid D-Bus response payload")
            payload = json.loads(data[0])
        return Target.parse(payload)
    except (OSError, TimeoutError, ValueError) as error:
        log.debug("Recipient unavailable: %s", error)
        return None


def trusted_socket(path: Path) -> bool:
    try:
        parent, socket = path.parent.stat(), path.lstat()
    except OSError as error:
        log.debug("Routing socket unavailable: %s", error)
        return False
    return (
        parent.st_uid == 0
        and not parent.st_mode & 0o022
        and socket.st_uid == 0
        and stat.S_ISSOCK(socket.st_mode)
    )


async def serve(desktop: str, path: Path = SOCKET) -> None:
    if not trusted_socket(path):
        raise OSError("Routing socket or containing directory is not trusted")
    reader, writer = await asyncio.open_unix_connection(str(path), limit=4096)
    try:
        writer.write(b'routing {"version":1,"kind":"hello"}\n')
        await writer.drain()
        while line := await reader.readline():
            if not line.startswith(b"routing "):
                continue
            request = json.loads(line[8:])
            if not isinstance(request, dict):
                raise ValueError("Invalid routing request")
            token = request.get("token")
            if (
                request.get("version") != 1
                or request.get("kind") != "query"
                or not isinstance(token, str)
                or len(token) != 16
                or any(c not in "0123456789abcdef" for c in token)
            ):
                raise ValueError("Invalid routing request")
            snapshot = await target(desktop)
            result = (
                None
                if snapshot is None
                else {
                    "session": snapshot.session,
                    "surface": snapshot.surface,
                    "app": snapshot.app,
                }
            )
            reply = {"version": 1, "kind": "reply", "token": token, "target": result}
            writer.write(("routing " + json.dumps(reply) + "\n").encode())
            await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def run(desktop: str) -> None:
    while True:
        try:
            await serve(desktop)
        except (OSError, ValueError) as error:
            log.warning("Routing helper disconnected: %s", error)
        await asyncio.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(os.environ.get("XDG_CURRENT_DESKTOP", "")))


if __name__ == "__main__":
    main()
