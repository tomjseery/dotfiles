"""Inside-sandbox actor. Invoke through run.py, never against an inherited session."""

import asyncio
import json
import os
import secrets
import sys
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

LAB = Path("/lab")
RUNTIME = LAB / "runtime"
INTERFACE = "org.tomjseery.MouseTarget"
APP = "mmb-native-probe"
type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


class Backend(StrEnum):
    KWIN = "kwin"
    HYPRLAND = "hyprland"


@dataclass(frozen=True)
class Target:
    session: str
    surface: str
    app: str


@dataclass(frozen=True)
class Invalidation:
    session: str
    generation: int


def object_json(text: str) -> dict[str, Json]:
    value = cast(Json, json.loads(text))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def target_json(text: str) -> Target | None:
    if json.loads(text) is None:
        return None
    value = object_json(text)
    if set(value) != {"session", "surface", "app"}:
        raise ValueError(f"unexpected target fields: {value}")
    fields = [value[key] for key in ("session", "surface", "app")]
    if not all(isinstance(field, str) and field for field in fields):
        raise ValueError("target fields must be nonempty strings")
    return Target(*cast(list[str], fields))


class Actor:
    def __init__(self, backend: Backend) -> None:
        self.backend = backend
        self.result: dict[str, object] = {"backend": backend, "passed": False}
        self.events: list[Invalidation] = []
        self.processes: list[asyncio.subprocess.Process] = []
        self.files = ExitStack()
        self.bus: MessageBus | None = None
        self.client: asyncio.subprocess.Process | None = None
        self.collector: asyncio.Task[None] | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.instance = ""
        self.commands: list[dict[str, object]] = []

    async def spawn(
        self, name: str, *command: str, pipes: bool = False
    ) -> asyncio.subprocess.Process:
        log = self.files.enter_context((LAB / f"{name}.log").open("w"))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE if pipes else log,
            stdin=asyncio.subprocess.PIPE if pipes else None,
            stderr=log,
        )
        self.processes.append(process)
        return process

    async def call(
        self,
        destination: str,
        path: str,
        interface: str,
        member: str,
        signature: str = "",
        body: list[object] | None = None,
    ) -> list[object]:
        if self.bus is None:
            raise RuntimeError("bus is not connected")
        reply = await asyncio.wait_for(
            self.bus.call(
                Message(
                    destination=destination,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                )
            ),
            4,
        )
        if reply is None or reply.message_type != MessageType.METHOD_RETURN:
            raise RuntimeError(f"D-Bus {member}: {reply}")
        return cast(list[object], reply.body)

    async def command(self, *command: str) -> str:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.processes.append(process)
        stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
        evidence: dict[str, object] = {
            "argv": command,
            "exit": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
        }
        self.commands.append(evidence)
        if process.returncode:
            raise RuntimeError(f"command failed: {evidence}")
        return stdout.decode().strip()

    async def ctl(self, *args: str) -> str:
        return await self.command("/usr/bin/hyprctl", "-i", self.instance, *args)

    async def target(self) -> Target | None:
        if self.backend == Backend.HYPRLAND:
            return target_json(await self.ctl("mouse-target"))
        reply = await self.call(INTERFACE, "/MouseTarget", INTERFACE, "target")
        if len(reply) != 1 or not isinstance(reply[0], str):
            raise RuntimeError("target method did not return one JSON string")
        return target_json(reply[0])

    def signal(self, message: Message) -> None:
        if (
            message.message_type == MessageType.SIGNAL
            and message.interface == INTERFACE
            and message.member == "changed"
        ):
            if (
                message.signature != "st"
                or len(message.body) != 2
                or not isinstance(message.body[0], str)
                or type(message.body[1]) is not int
            ):
                raise RuntimeError("invalid changed signal signature")
            self.events.append(Invalidation(message.body[0], message.body[1]))

    async def start_kwin(self) -> None:
        kwin = await self.spawn(
            "kwin",
            "/usr/bin/kwin_wayland",
            "--virtual",
            "--width",
            "800",
            "--height",
            "600",
            "--socket",
            "mmb-parent-wayland",
            "--no-lockscreen",
            "--no-global-shortcuts",
            "--no-kactivities",
        )
        self.bus = await MessageBus().connect()
        for _ in range(250):
            owners = await self.call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
            )
            if (
                "org.kde.KWin" in cast(list[str], owners[0])
                and (RUNTIME / "mmb-parent-wayland").is_socket()
            ):
                break
            if kwin.returncode is not None:
                raise RuntimeError(f"KWin exited {kwin.returncode}")
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("org.kde.KWin / owned display startup timeout")
        self.result["kwin_bus_and_socket_ready"] = True
        # /Effects readiness is recorded before waiting for the bridge name.
        props = await self.call(
            "org.kde.KWin",
            "/Effects",
            "org.freedesktop.DBus.Properties",
            "GetAll",
            "s",
            ["org.kde.kwin.Effects"],
        )
        self.result["effects_ready"] = True
        if self.backend == Backend.KWIN:
            loaded = props[0]
            # D-Bus Variant is unwrapped only at this external API boundary.
            from dbus_fast import Variant

            if not isinstance(loaded, dict):
                raise RuntimeError("invalid Effects properties")
            effects = loaded.get("loadedEffects")
            if not isinstance(effects, Variant) or "mousetarget" not in effects.value:
                raise RuntimeError("mousetarget effect was not loaded")
            self.result["plugin_discovered_and_loaded"] = True
            for _ in range(100):
                names = await self.call(
                    "org.freedesktop.DBus",
                    "/org/freedesktop/DBus",
                    "org.freedesktop.DBus",
                    "ListNames",
                )
                if INTERFACE in cast(list[str], names[0]):
                    break
                await asyncio.sleep(0.05)
            else:
                raise RuntimeError("MouseTarget service readiness timeout")
            self.result["target_service_ready"] = True
            self.bus.add_message_handler(self.signal)
            await self.call(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "AddMatch",
                "s",
                [
                    f"type='signal',interface='{INTERFACE}',member='changed'",
                ],
            )
            self.result["subscription_barrier"] = "AddMatch method reply"

    async def start_hyprland(self) -> Path:
        process = await self.spawn(
            "hyprland", "/usr/bin/Hyprland", "--config", "/lab/config/hyprland.lua"
        )
        for _ in range(250):
            sockets = list((RUNTIME / "hypr").glob("*/.socket.sock"))
            if len(sockets) == 1:
                self.instance = sockets[0].parent.name
                break
            if process.returncode is not None:
                raise RuntimeError(f"Hyprland exited {process.returncode}")
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("contained Hyprland startup timeout")
        self.result["hyprland_version"] = await self.ctl("version")
        errors = await self.ctl("configerrors")
        if errors:
            raise RuntimeError(f"Hyprland config errors: {errors}")
        if await self.ctl("plugin", "load", "/lab/mouse_target_hyprland.so") != "ok":
            raise RuntimeError("plugin load failed")
        reader, self.writer = await asyncio.open_unix_connection(
            str(RUNTIME / "hypr" / self.instance / ".socket2.sock")
        )
        token = secrets.token_hex(16)
        if await self.ctl("mouse-target-observe", token) != "ok":
            raise RuntimeError("observation command failed")

        async def ready() -> None:
            while line := await reader.readline():
                if line.decode().strip() == f"mouse-target-ready>>{token}":
                    return
            raise RuntimeError("Socket2 closed before readiness event")

        await asyncio.wait_for(ready(), 4)
        self.result["subscription_barrier"] = "matching mouse-target-ready token"

        async def collect() -> None:
            while line := await reader.readline():
                text = line.decode().strip()
                if text.startswith("mouse-target-changed>>"):
                    event = object_json(text.split(">>", 1)[1])
                    session, generation = event.get("session"), event.get("generation")
                    if not isinstance(session, str) or type(generation) is not int:
                        raise RuntimeError("invalid Socket2 invalidation")
                    self.events.append(Invalidation(session, generation))
            raise RuntimeError("Socket2 closed during observation")

        self.collector = asyncio.create_task(collect())
        sockets = [path for path in RUNTIME.glob("wayland-*") if path.is_socket()]
        if len(sockets) != 1:
            raise RuntimeError(
                f"expected one private Hyprland display, found {sockets}"
            )
        return sockets[0]

    async def client_command(self, command: str) -> None:
        if (
            self.client is None
            or self.client.stdin is None
            or self.client.stdout is None
        ):
            raise RuntimeError("client pipes unavailable")
        self.client.stdin.write((command + "\n").encode())
        await self.client.stdin.drain()
        if await asyncio.wait_for(self.client.stdout.readline(), 4) != b"done\n":
            raise RuntimeError(f"client command failed: {command}")

    async def move(self, x: int, y: int) -> None:
        before = len(self.events)
        await self.client_command(f"move {x} {y}")
        for _ in range(150):
            if self.collector is not None and self.collector.done():
                self.collector.result()
            if len(self.events) > before:
                return
            await asyncio.sleep(0.01)
        raise RuntimeError(f"missing focus invalidation after move to {x},{y}")

    async def root_probe(self, socket: Path) -> None:
        self.client = await self.spawn(
            "client", "/lab/client", str(socket), self.backend, pipes=True
        )
        if (
            self.client.stdout is None
            or await asyncio.wait_for(self.client.stdout.readline(), 5) != b"ready\n"
        ):
            raise RuntimeError("disposable root client did not become ready")
        await self.client_command("sync")
        await self.client_command("sync")
        if self.backend == Backend.KWIN:
            for title, x in (("MMB Lab A", 50), ("MMB Lab B", 450)):
                await self.command(
                    "/usr/bin/kdotool",
                    "search",
                    "--name",
                    title,
                    "windowmove",
                    str(x),
                    "100",
                    "windowsize",
                    "300",
                    "200",
                )
            await self.client_command("sync")
            await asyncio.sleep(0.1)
            for title in ("MMB Lab A", "MMB Lab B"):
                geometry = await self.command(
                    "/usr/bin/kdotool", "search", "--name", title, "getwindowgeometry"
                )
                self.result[title] = geometry
            a, b, empty = (150, 180), (550, 180), (790, 590)
        else:
            clients = cast(
                list[dict[str, Json]], json.loads(await self.ctl("-j", "clients"))
            )
            self.result["client_geometry"] = clients
            self.result["monitors"] = json.loads(await self.ctl("-j", "monitors"))
            centers: dict[str, tuple[int, int]] = {}
            for window in clients:
                window_title = window.get("title")
                if isinstance(window_title, str) and window_title in (
                    "MMB Lab A",
                    "MMB Lab B",
                ):
                    at = cast(list[int], window["at"])
                    size = cast(list[int], window["size"])
                    centers[window_title] = (
                        at[0] + size[0] // 2,
                        at[1] + size[1] // 2,
                    )
            if len(centers) != 2:
                raise RuntimeError("both disposable roots must be mapped")
            a, b, empty = centers["MMB Lab A"], centers["MMB Lab B"], (0, 0)
        self.result["test_centers"] = {"A": a, "B": b, "empty": empty}
        await self.move(*a)
        first = await self.target()
        before = len(self.events)
        await self.move(*b)
        await self.move(*a)  # Deliberately no query while B owns pointer focus.
        again = await self.target()
        if first is None or again is None:
            raise RuntimeError("root content target was null")
        self.result["first_A"] = asdict(first)
        self.result["returned_A"] = asdict(again)
        if not (
            first.app == again.app == APP
            and first.session == again.session
            and first.surface != again.surface
            and len(self.events) >= before + 2
        ):
            raise RuntimeError(
                "A-B-A identity/generation/invalidation acceptance failed"
            )
        for previous, current in zip(self.events, self.events[1:], strict=False):
            if (
                previous.session != current.session
                or previous.generation >= current.generation
            ):
                raise RuntimeError("focus generations did not strictly increase")
        self.result["A_B_A_without_B_query"] = True
        await self.move(*empty)
        if await self.target() is not None:
            raise RuntimeError("empty area target must be null")
        self.result["empty_target"] = None
        if self.client.stdin is None:
            raise RuntimeError("client stdin unavailable")
        self.client.stdin.write(b"quit\n")
        await self.client.stdin.drain()
        await asyncio.wait_for(self.client.wait(), 4)
        if self.client.returncode != 0:
            raise RuntimeError(f"client exited {self.client.returncode}")
        self.result["client_exit"] = 0

    async def final_invalidation(self) -> None:
        await asyncio.sleep(
            0.1
        )  # Drain surface-destruction notifications before teardown.
        before = len(self.events)
        if self.backend == Backend.HYPRLAND:
            if (
                await self.ctl("plugin", "unload", "/lab/mouse_target_hyprland.so")
                != "ok"
            ):
                raise RuntimeError("owned plugin unload failed")
        else:
            await self.call(
                "org.kde.KWin",
                "/Effects",
                "org.kde.kwin.Effects",
                "unloadEffect",
                "s",
                ["mousetarget"],
            )
        for _ in range(100):
            if len(self.events) > before:
                self.result["final_invalidation"] = asdict(self.events[-1])
                return
            await asyncio.sleep(0.01)
        raise RuntimeError("missing final bridge invalidation")

    async def cleanup(self) -> None:
        if self.collector is not None:
            self.collector.cancel()
            await asyncio.gather(self.collector, return_exceptions=True)
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        for process in reversed(self.processes):
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
        if self.bus is not None:
            self.bus.disconnect()
        self.files.close()

    async def run(self, render_node: str) -> bool:
        containment = {
            "uid": os.getuid(),
            "input_absent": not Path("/dev/input").exists(),
            "uinput_absent": not Path("/dev/uinput").exists(),
            "system_bus_absent": not Path("/run/dbus/system_bus_socket").exists(),
            "seatd_absent": not Path("/run/seatd.sock").exists(),
            "render_nodes": sorted(path.name for path in Path("/dev/dri").iterdir()),
            "runtime": os.environ.get("XDG_RUNTIME_DIR"),
            "display": os.environ.get("WAYLAND_DISPLAY"),
        }
        self.result["containment"] = containment
        (LAB / "containment.json").write_text(json.dumps(containment, indent=2) + "\n")
        try:
            if (
                not all(
                    containment[key]
                    for key in (
                        "input_absent",
                        "uinput_absent",
                        "system_bus_absent",
                        "seatd_absent",
                    )
                )
                or containment["render_nodes"] != [render_node]
                or containment["runtime"] != str(RUNTIME)
                or containment["display"] != "mmb-parent-wayland"
            ):
                raise RuntimeError(
                    "containment preconditions failed; no compositor launched"
                )
            await self.start_kwin()
            socket = RUNTIME / "mmb-parent-wayland"
            if self.backend == Backend.HYPRLAND:
                socket = await self.start_hyprland()
            initial = await self.target()
            self.result["initial_target"] = asdict(initial) if initial else None
            if initial is not None:
                raise RuntimeError("initial empty compositor target must be null")
            await self.root_probe(socket)
            await self.final_invalidation()
            self.result["passed"] = True
        except (RuntimeError, ValueError, TimeoutError, OSError) as error:
            self.result["failure"] = f"{type(error).__name__}: {error}"
        finally:
            await self.cleanup()
            self.result["events"] = [asdict(event) for event in self.events]
            self.result["commands"] = self.commands
            (LAB / "result.json").write_text(json.dumps(self.result, indent=2) + "\n")
        return self.result["passed"] is True


if __name__ == "__main__":
    if len(sys.argv) != 3 or Path(__file__).parent != Path("/harness"):
        sys.exit("Use run.py to establish containment")
    sys.exit(0 if asyncio.run(Actor(Backend(sys.argv[1])).run(sys.argv[2])) else 1)
