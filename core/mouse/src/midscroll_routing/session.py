"""Read native compositor recipient snapshots and answer daemon requests."""

import asyncio
import json
import logging
import os
import re
import secrets
import stat
from collections.abc import Callable
from pathlib import Path

from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.errors import DBusFastError

from midscroll_routing import Target

log = logging.getLogger(__name__)
SOCKET = Path("/run/midscroll/state.sock")
SERVICE = "org.tomjseery.MouseTarget"


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
        root_owner = namespace_root_uid(
            Path("/proc/self/uid_map").read_text(encoding="utf-8"),
            int(Path("/proc/sys/kernel/overflowuid").read_text(encoding="utf-8")),
        )
        parent, socket = path.parent.stat(), path.lstat()
    except (OSError, ValueError) as error:
        log.debug("Routing socket unavailable: %s", error)
        return False
    return (
        parent.st_uid == root_owner
        and not path.parent.is_symlink()
        and not parent.st_mode & 0o022
        and socket.st_uid == root_owner
        and stat.S_ISSOCK(socket.st_mode)
    )


def namespace_root_uid(mapping: str, overflow: int) -> int:
    for line in mapping.splitlines():
        inside, outside, count = (int(value) for value in line.split())
        if outside == 0 and count > 0:
            return inside
    return overflow


async def observe_kde(notify: Callable[[], None], ready: asyncio.Event) -> None:
    bus = await MessageBus(auth_timeout=1).connect()

    def received(message: Message) -> None:
        if message.message_type is not MessageType.SIGNAL:
            return
        if message.interface == SERVICE and message.member == "changed":
            notify()
            if message.signature != "st":
                bus.disconnect()
        elif (
            message.interface == "org.freedesktop.DBus"
            and message.member == "NameOwnerChanged"
            and message.body
            and message.body[0] == SERVICE
        ):
            notify()
            bus.disconnect()

    bus.add_message_handler(received)
    try:
        for rule in [
            f"type='signal',sender='{SERVICE}',path='/MouseTarget',interface='{SERVICE}',member='changed'",
            f"type='signal',sender='org.freedesktop.DBus',interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0='{SERVICE}'",
        ]:
            reply = await bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[rule],
                )
            )
            if reply.message_type is MessageType.ERROR:
                raise OSError("Compositor event subscription failed")
        ready.set()
        # dbus-fast 5.2 exposes this public coroutine without a return annotation.
        await bus.wait_for_disconnect()  # type: ignore[no-untyped-call]
        raise OSError("Compositor event subscription disconnected")
    finally:
        bus.disconnect()


async def observe_hyprland(notify: Callable[[], None], ready: asyncio.Event) -> None:
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", signature):
        raise OSError("Hyprland instance signature is unavailable")
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    path = runtime / "hypr" / signature / ".socket2.sock"
    reader, writer = await asyncio.open_unix_connection(str(path), limit=4096)
    token = secrets.token_hex(16)
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            "hyprctl",
            "mouse-target-observe",
            token,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async for line in reader:
            if line == f"mouse-target-ready>>{token}\n".encode():
                ready.set()
            elif line.startswith(b"mouse-target-changed>>"):
                notify()
                event = json.loads(line.split(b">>", 1)[1])
                if (
                    not isinstance(event, dict)
                    or not isinstance(event.get("session"), str)
                    or type(event.get("generation")) is not int
                ):
                    raise ValueError("Malformed compositor invalidation")
        raise OSError("Compositor event stream disconnected")
    finally:
        writer.close()
        await writer.wait_closed()
        if process is not None:
            if process.returncode is None:
                process.kill()
            await process.wait()


async def observe(
    desktop: str, notify: Callable[[], None], ready: asyncio.Event
) -> None:
    desktops = desktop.casefold().split(":")
    if "kde" in desktops:
        await observe_kde(notify, ready)
    elif "hyprland" in desktops:
        await observe_hyprland(notify, ready)
    else:
        raise OSError("No supported compositor event interface")


async def renderer_pid(bus: MessageBus) -> int | None:
    """Resolve a loaded renderer against one unique KWin bus connection."""

    async def call(
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str,
        body: list[object],
        expected: str,
    ) -> object:
        reply = await bus.call(
            Message(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                signature=signature,
                body=body,
            )
        )
        if (
            reply is None
            or reply.message_type is not MessageType.METHOD_RETURN
            or reply.signature != expected
            or len(reply.body) != 1
        ):
            raise ValueError(f"Invalid renderer {member} reply")
        return reply.body[0]

    async def owner() -> object:
        return await call(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetNameOwner",
            "s",
            ["org.kde.KWin"],
            "s",
        )

    unique = await owner()
    if not isinstance(unique, str) or not unique.startswith(":"):
        raise ValueError("Invalid unique KWin owner")
    loaded = await call(
        unique,
        "/Effects",
        "org.kde.kwin.Effects",
        "isEffectLoaded",
        "s",
        ["midscrollcursor"],
        "b",
    )
    if type(loaded) is not bool:
        raise ValueError("Invalid renderer loaded state")
    if not loaded:
        return None
    pid = await call(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "GetConnectionUnixProcessID",
        "s",
        [unique],
        "u",
    )
    if type(pid) is not int or not 0 < pid <= 0xFFFFFFFF:
        raise ValueError("Invalid renderer process ID")
    # The well-known name may have changed while the unique connection survived.
    return pid if await owner() == unique else None


async def renderer_monitor(desktop: str, writer: asyncio.StreamWriter) -> None:
    """Report effect availability; this is not a rendered-frame acknowledgement."""
    bus: MessageBus | None = None
    try:
        if "kde" in desktop.casefold().split(":"):
            bus = MessageBus(auth_timeout=1)
            await asyncio.wait_for(bus.connect(), 1)
        while True:
            pid = None
            if bus is not None:
                try:
                    pid = await asyncio.wait_for(renderer_pid(bus), 0.15)
                except (TimeoutError, ValueError) as error:
                    log.debug("Renderer unavailable: %s", error)
            if writer.transport.get_write_buffer_size() > 4096:
                raise OSError("Renderer report channel is backed up")
            report = {"version": 1, "pid": pid}
            writer.write(("renderer " + json.dumps(report) + "\n").encode())
            await writer.drain()
            await asyncio.sleep(0.25)
    finally:
        if bus is not None:
            bus.disconnect()


async def serve(desktop: str, path: Path = SOCKET) -> None:
    if not trusted_socket(path):
        raise OSError("Routing socket or containing directory is not trusted")
    reader, writer = await asyncio.open_unix_connection(str(path), limit=4096)

    def invalidate() -> None:
        if writer.transport.get_write_buffer_size() > 4096:
            writer.close()
        else:
            writer.write(b'routing {"version":1,"kind":"target","target":null}\n')

    ready = asyncio.Event()
    monitor = asyncio.create_task(observe(desktop, invalidate, ready))
    readiness = asyncio.create_task(ready.wait())
    request_task: asyncio.Task[None] | None = None
    renderer_task: asyncio.Task[None] | None = None
    try:
        completed, _ = await asyncio.wait(
            {monitor, readiness}, timeout=1, return_when=asyncio.FIRST_COMPLETED
        )
        if monitor in completed:
            monitor.result()
        if not ready.is_set():
            raise OSError("Compositor observation is not ready")
        writer.write(b'routing {"version":1,"kind":"hello"}\n')
        await writer.drain()
        request_task = asyncio.create_task(answer(desktop, reader, writer))
        renderer_task = asyncio.create_task(renderer_monitor(desktop, writer))
        completed, _ = await asyncio.wait(
            {monitor, request_task, renderer_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in completed:
            task.result()
    finally:
        tasks = [monitor, readiness]
        if request_task is not None:
            tasks.append(request_task)
        if renderer_task is not None:
            tasks.append(renderer_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        await writer.wait_closed()


async def answer(
    desktop: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
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


async def run(desktop: str) -> None:
    while True:
        try:
            await serve(desktop)
        except (OSError, ValueError, EOFError, TimeoutError, DBusFastError) as error:
            log.warning("Routing helper disconnected: %s", error)
        await asyncio.sleep(2)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(os.environ.get("XDG_CURRENT_DESKTOP", "")))


if __name__ == "__main__":
    main()
