import asyncio
import json
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

        monkeypatch.setattr(session, "target", query)
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
