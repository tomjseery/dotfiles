import asyncio
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from midscroll_routing import Target, session


@pytest.mark.parametrize("desktop", ["KDE", "Hyprland"])
def test_session_reads_native_bridge_and_preserves_identity(
    desktop: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"session": "session", "surface": "surface", "app": "Kitty"}
    encoded = json.dumps(payload).encode()
    if desktop == "KDE":
        encoded = json.dumps({"type": "s", "data": [encoded.decode()]}).encode()
    commands: list[tuple[str, ...]] = []

    class Process:
        returncode: int | None = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return encoded, b""

    async def launch(*command: str, stdout: int, stderr: int) -> Process:
        commands.append(command)
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    assert asyncio.run(session.target(desktop)) == Target("session", "surface", "kitty")
    assert commands[0][0] == ("busctl" if desktop == "KDE" else "hyprctl")
    assert "clients" not in commands[0]
    assert "getwindowclassname" not in commands[0]


def test_unknown_desktop_never_spawns_a_target_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("Unknown desktops must stay native")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unexpected)
    assert asyncio.run(session.target("unknown")) is None


@pytest.mark.parametrize(
    ("mapping", "expected"),
    [("0 0 4294967295\n", 0), ("1000 1000 1\n", 65534), ("42 0 1\n", 42)],
)
def test_socket_root_identity_respects_user_namespace(
    mapping: str, expected: int
) -> None:
    assert session.namespace_root_uid(mapping, 65534) == expected


def test_bridge_timeout_kills_and_reaps_owned_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class Process:
        returncode: int | None = None

        async def communicate(self) -> tuple[bytes, bytes]:
            raise TimeoutError("test deadline")

        def kill(self) -> None:
            events.append("kill")

        async def wait(self) -> int:
            events.append("wait")
            self.returncode = -9
            return -9

    async def launch(*args: object, **kwargs: object) -> Process:
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    assert asyncio.run(session.target("Hyprland")) is None
    assert events == ["kill", "wait"]


@pytest.mark.parametrize("body", [b"invalid", b"null", b"{}", b'{"app":"kitty"}'])
def test_invalid_or_unknown_bridge_response_never_grants_fallback(
    body: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        returncode = 0

        async def communicate(self) -> tuple[bytes, bytes]:
            return body, b""

    async def launch(*args: object, **kwargs: object) -> Process:
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    assert asyncio.run(session.target("Hyprland")) is None


def test_session_serves_real_socket_without_drawing_or_focus_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        requests: list[str] = []
        complete = asyncio.Event()

        async def query(desktop: str) -> Target:
            return Target("test-session", "window", "kitty")

        async def observer(desktop: str, notify: object, ready: asyncio.Event) -> None:
            ready.set()
            await asyncio.Future[None]()

        monkeypatch.setattr(session, "target", query)
        monkeypatch.setattr(session, "observe", observer)
        monkeypatch.setattr(session, "trusted_socket", lambda _: True)

        async def daemon(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            try:
                requests.append((await reader.readline()).decode())
                writer.write(
                    b'routing {"version":1,"kind":"query","token":"0123456789abcdef"}\n'
                )
                await writer.drain()
                requests.append((await reader.readline()).decode())
            finally:
                writer.close()
                await writer.wait_closed()
                complete.set()

        path = tmp_path / "state.sock"
        server = await asyncio.start_unix_server(daemon, path=str(path))
        async with server:
            await session.serve("KDE", path)
            await complete.wait()
        hello = json.loads(requests[0][8:])
        reply = json.loads(requests[1][8:])
        assert hello == {"version": 1, "kind": "hello"}
        assert reply["target"] == {
            "session": "test-session",
            "surface": "window",
            "app": "kitty",
        }
        assert reply["token"] == "0123456789abcdef"

    asyncio.run(scenario())


def test_observation_failure_never_registers_routing_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        received: list[bytes] = []
        closed = asyncio.Event()

        async def daemon(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            received.append(await reader.read())
            writer.close()
            await writer.wait_closed()
            closed.set()

        async def unavailable(
            desktop: str, notify: Callable[[], None], ready: asyncio.Event
        ) -> None:
            raise OSError("Compositor event interface absent")

        monkeypatch.setattr(session, "trusted_socket", lambda _: True)
        monkeypatch.setattr(session, "observe", unavailable)
        path = tmp_path / "state.sock"
        server = await asyncio.start_unix_server(daemon, path=str(path))
        async with server:
            with pytest.raises(OSError, match="event interface"):
                await session.serve("KDE", path)
            await closed.wait()
        assert received == [b""]

    asyncio.run(scenario())


def test_hyprland_observation_waits_for_matching_barrier_and_reports_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        runtime = tmp_path / "hypr" / "test-instance"
        runtime.mkdir(parents=True)
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "test-instance")
        connected = asyncio.Event()
        finished = asyncio.Event()
        ready = asyncio.Event()
        channels: list[asyncio.StreamWriter] = []
        notifications: list[bool] = []

        async def compositor(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            channels.append(writer)
            connected.set()
            await finished.wait()
            writer.close()
            await writer.wait_closed()

        class Process:
            returncode = 0

            async def wait(self) -> int:
                return 0

        async def launch(*command: str, **kwargs: object) -> Process:
            await connected.wait()
            assert command[:2] == ("hyprctl", "mouse-target-observe")
            assert not ready.is_set()
            channels[0].write(f"mouse-target-ready>>{command[2]}\n".encode())
            channels[0].write(b'mouse-target-changed>>{"session":"s","generation":2}\n')
            await channels[0].drain()
            return Process()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
        server = await asyncio.start_unix_server(
            compositor, path=str(runtime / ".socket2.sock")
        )
        async with server:
            task = asyncio.create_task(
                session.observe_hyprland(lambda: notifications.append(True), ready)
            )
            await asyncio.wait_for(ready.wait(), 1)

            async def notified() -> None:
                while not notifications:
                    await asyncio.sleep(0)

            await asyncio.wait_for(notified(), 1)
            finished.set()
            with pytest.raises(OSError, match="disconnected"):
                await task
        assert notifications == [True]

    asyncio.run(scenario())
