import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest

from midscroll_routing import Gesture, session
from midscroll_routing.presentation import ACCEPTED


@pytest.mark.parametrize(
    "case", ["normal", "missing", "lost", "mismatched", "unregistered"]
)
def test_native_presentation_requires_correlated_live_renderer(
    engine: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    async def scenario() -> None:
        monkeypatch.setattr(engine, "_uid_has_seat", lambda _: True)
        monkeypatch.setattr(engine, "_uid_is_active", lambda _: True)
        monkeypatch.setattr(engine, "_peer_is_overlay", lambda _: True)
        # Credential PIDs are the external boundary; framing, admission,
        # registration, correlation and revocation use production code.
        monkeypatch.setattr(engine, "_peer_pid", lambda _: 101)
        notifier = engine.Notifier(engine.FocusFilter())
        path = str(tmp_path / "state.sock")
        server = await asyncio.start_unix_server(notifier._client, path=path)
        async with server:
            viewer, viewer_writer = await asyncio.open_unix_connection(path)
            assert await viewer.readline() == b"0\n"
            monkeypatch.setattr(engine, "_peer_pid", lambda _: 202)
            router, router_writer = await asyncio.open_unix_connection(path)
            assert await router.readline() == b"0\n"
            if case != "unregistered":
                router_writer.write(b'routing {"version":1,"kind":"hello"}\n')
            pid = None if case == "missing" else 999 if case == "mismatched" else 101
            router_writer.write(
                ("renderer " + json.dumps({"version": 1, "pid": pid}) + "\n").encode()
            )
            await router_writer.drain()
            if case == "unregistered":
                assert await router.readline() == b""
            else:

                async def reported() -> None:
                    while not notifier.presentation.renderers:
                        await asyncio.sleep(0)

                await asyncio.wait_for(reported(), 1)
            monkeypatch.setattr(engine, "_peer_is_overlay", lambda _: False)
            native, native_writer = await asyncio.open_unix_connection(path)
            if case in {"normal", "lost"}:
                native_writer.write(b'presentation {"version":1,"active":true}\n')
                await native_writer.drain()
                assert await native.readline() == ACCEPTED
                notifier.set(False)
                assert await viewer.readline() == b"1\n"
                assert notifier.msg == b"0\n"
                if case == "lost":
                    viewer_writer.close()
                    await viewer_writer.wait_closed()

                    async def renderer_closed() -> None:
                        while 101 in notifier.control_pids.values():
                            await asyncio.sleep(0)

                    await asyncio.wait_for(renderer_closed(), 1)
                    native_writer.write(b'presentation {"version":1,"active":true}\n')
                else:
                    # A presenter can never become a routing authority.
                    native_writer.write(b'routing {"version":1,"kind":"hello"}\n')
                await native_writer.drain()
            assert await native.readline() == b""
            assert not notifier.presentation.leases
            assert len(notifier.routing.routers) == (0 if case == "unregistered" else 1)
            if case == "normal":
                notifier.set(False)
                assert await viewer.readline() == b"0\n"
            for writer in (native_writer, viewer_writer, router_writer):
                writer.close()
                await writer.wait_closed()

            async def disconnected() -> None:
                while notifier.writers or notifier.presentation.peers:
                    await asyncio.sleep(0)

            await asyncio.wait_for(disconnected(), 1)

    asyncio.run(scenario())


def test_real_ipc_with_passive_viewer_and_router(
    engine: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        # Only identity/environment boundaries are controlled; parsing and Unix
        # framing use the production handler and real OS peer credentials.
        monkeypatch.setattr(engine, "_uid_has_seat", lambda _: True)
        monkeypatch.setattr(engine, "_uid_is_active", lambda _: True)
        monkeypatch.setattr(engine, "_peer_is_overlay", lambda _: True)
        notifier = engine.Notifier(engine.FocusFilter())
        path = str(tmp_path / "state.sock")
        server = await asyncio.start_unix_server(
            notifier._client, path=path, limit=engine.SOCK_LIMIT
        )
        async with server:
            reader, writer = await asyncio.open_unix_connection(path)
            viewer, viewer_writer = await asyncio.open_unix_connection(path)
            await reader.readline()
            await viewer.readline()
            writer.write(b'routing {"version":1,"kind":"hello"}\n')
            await writer.drain()

            # Registration barrier without assuming scheduler timing.
            async def registered() -> None:
                while not notifier.routing.routers:
                    await asyncio.sleep(0)

            await asyncio.wait_for(registered(), 1)
            query = asyncio.create_task(notifier.routing.query())
            message = json.loads((await reader.readline())[8:])
            writer.write(
                (
                    "routing "
                    + json.dumps(
                        {
                            "version": 1,
                            "kind": "reply",
                            "token": message["token"],
                            "target": {
                                "session": "test",
                                "surface": "id",
                                "app": "kitty",
                            },
                        }
                    )
                    + "\n"
                ).encode()
            )
            await writer.drain()
            assert await query is not None
            # A passive viewer receives notifications but no routing request.
            notifier.set(True)
            assert await viewer.readline() == b"1\n"
            writer.close()
            viewer_writer.close()
            await writer.wait_closed()
            await viewer_writer.wait_closed()

            async def disconnected() -> None:
                while notifier.writers:
                    await asyncio.sleep(0)

            await asyncio.wait_for(disconnected(), 1)
            assert not notifier.routing.routers

    asyncio.run(scenario())


@pytest.mark.parametrize("app", ["future-browser", "kitty", None])
def test_production_pump_forwards_balanced_sequences_and_frames(
    engine: ModuleType, monkeypatch: pytest.MonkeyPatch, app: str | None
) -> None:
    async def scenario() -> None:
        output: list[tuple[int, int, int] | str] = []
        ui = SimpleNamespace(
            device=None,
            write=lambda *event: output.append(event),
            syn=lambda: output.append("syn"),
            close=lambda: None,
        )
        monkeypatch.setattr(engine, "make_uinput", lambda _: ui)
        notifier = engine.Notifier(engine.FocusFilter())

        # External query boundary; the pump, release ledger, frame forwarding,
        # normal movement and cleanup are the production implementation.
        async def query() -> Any:
            from midscroll_routing import Lease, Target

            if app is None:
                return None
            if app != "kitty":
                return None
            return Lease(peer, Target("test", "id", app), float("inf"))

        peer = cast(asyncio.StreamWriter, object())
        # The lease's socket eligibility is this test's external boundary.
        notifier.routing.eligible = lambda _: True
        notifier.routing.routers.add(peer)
        notifier.routing.query = query
        states: dict[str, Any] = {}
        middle = engine.e.BTN_MIDDLE
        events = [
            (engine.e.EV_KEY, middle, 1),
            (engine.e.EV_SYN, 0, 0),
            (engine.e.EV_REL, engine.e.REL_X, 2),
            (engine.e.EV_SYN, 0, 0),
            (engine.e.EV_KEY, middle, 0),
            (engine.e.EV_SYN, 0, 0),
        ]

        class Device:
            name = "synthetic"
            phys = "synthetic"

            def grab(self) -> None:
                pass

            def close(self) -> None:
                pass

            async def async_read_loop(self) -> AsyncIterator[SimpleNamespace]:
                for kind, code, value in events:
                    yield SimpleNamespace(type=kind, code=code, value=value)
                assert states["device"].scrolling is (app == "kitty")

        await engine.pump(
            "device", Device(), states, {}, notifier.focus, set(), notifier
        )
        native_buttons = [
            event
            for event in output
            if isinstance(event, tuple) and event[0] == engine.e.EV_KEY
        ]
        expected = (
            []
            if app == "kitty"
            else [(engine.e.EV_KEY, middle, 1), (engine.e.EV_KEY, middle, 0)]
        )
        assert native_buttons == expected
        assert (engine.e.EV_REL, engine.e.REL_X, 2) in output
        assert output.count("syn") == 3

    asyncio.run(scenario())


@pytest.mark.parametrize("still_held", [True, False])
def test_pump_dropped_report_releases_native_buttons(
    engine: ModuleType, monkeypatch: pytest.MonkeyPatch, still_held: bool
) -> None:
    async def scenario() -> None:
        output: list[tuple[int, int, int]] = []
        ui = SimpleNamespace(
            device=None,
            write=lambda *ev: output.append(ev),
            syn=lambda: None,
            close=lambda: None,
        )
        monkeypatch.setattr(engine, "make_uinput", lambda _: ui)
        notifier = engine.Notifier(engine.FocusFilter())
        left = engine.e.BTN_LEFT

        class Device:
            name, phys = "synthetic", "synthetic"

            def grab(self) -> None:
                pass

            def close(self) -> None:
                pass

            def active_keys(self) -> list[int]:
                return [left] if still_held else []

            async def async_read_loop(self) -> AsyncIterator[SimpleNamespace]:
                for kind, code, value in [
                    (engine.e.EV_KEY, left, 1),
                    (engine.e.EV_SYN, engine.e.SYN_DROPPED, 0),
                    (engine.e.EV_KEY, left, 0),
                ]:
                    yield SimpleNamespace(type=kind, code=code, value=value)
                assert output == [
                    (engine.e.EV_KEY, left, 1),
                    (engine.e.EV_KEY, left, 0),
                ]

        await engine.pump("device", Device(), {}, {}, notifier.focus, set(), notifier)

    asyncio.run(scenario())


def test_pump_unresolved_motion_never_uses_previous_pointer_target(
    engine: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        output: list[tuple[int, int, int]] = []
        ui = SimpleNamespace(
            device=None,
            write=lambda *ev: output.append(ev),
            syn=lambda: None,
            close=lambda: None,
        )
        monkeypatch.setattr(engine, "make_uinput", lambda _: ui)
        notifier = engine.Notifier(engine.FocusFilter())

        async def stale_query() -> None:
            pytest.fail("Unsubmitted motion cannot establish a pointer target")

        notifier.routing.query = stale_query
        middle = engine.e.BTN_MIDDLE

        class Device:
            name, phys = "synthetic", "synthetic"

            def grab(self) -> None:
                pass

            def close(self) -> None:
                pass

            async def async_read_loop(self) -> AsyncIterator[SimpleNamespace]:
                for kind, code, value in [
                    (engine.e.EV_REL, engine.e.REL_X, 100),
                    (engine.e.EV_KEY, middle, 1),
                    (engine.e.EV_SYN, 0, 0),
                    (engine.e.EV_KEY, middle, 0),
                    (engine.e.EV_SYN, 0, 0),
                ]:
                    yield SimpleNamespace(type=kind, code=code, value=value)

        await engine.pump("device", Device(), {}, {}, notifier.focus, set(), notifier)
        assert output == [
            (engine.e.EV_REL, engine.e.REL_X, 100),
            (engine.e.EV_KEY, middle, 1),
            (engine.e.EV_KEY, middle, 0),
        ]

    asyncio.run(scenario())


def test_composed_helper_invalidation_stops_fallback_between_queries(
    engine: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        changed = asyncio.Event()
        observed = asyncio.Event()
        monkeypatch.setattr(engine, "_uid_has_seat", lambda _: True)
        monkeypatch.setattr(engine, "_uid_is_active", lambda _: True)
        monkeypatch.setattr(engine, "_peer_is_overlay", lambda _: True)
        monkeypatch.setattr(session, "trusted_socket", lambda _: True)

        async def target(desktop: str) -> Any:
            from midscroll_routing import Target

            return Target("session", "same-original-window", "kitty")

        async def observe(desktop: str, notify: Any, ready: asyncio.Event) -> None:
            ready.set()
            await changed.wait()
            # Both transitions can occur before another target query.
            notify()
            notify()
            observed.set()
            await asyncio.Future[None]()

        monkeypatch.setattr(session, "target", target)
        monkeypatch.setattr(session, "observe", observe)
        notifier = engine.Notifier(engine.FocusFilter())
        path = tmp_path / "state.sock"
        server = await asyncio.start_unix_server(notifier._client, path=str(path))
        async with server:
            helper = asyncio.create_task(session.serve("KDE", path))
            try:

                async def registered() -> None:
                    while not notifier.routing.routers:
                        await asyncio.sleep(0)

                await asyncio.wait_for(registered(), 1)
                state = engine.State(SimpleNamespace())
                gesture = Gesture(state)
                assert await notifier.routing.button(gesture, engine.e.BTN_MIDDLE, 1)
                assert await notifier.routing.button(gesture, engine.e.BTN_MIDDLE, 0)
                assert state.scrolling
                changed.set()
                await observed.wait()

                async def revoked() -> None:
                    while notifier.routing.active is not None:
                        await asyncio.sleep(0)

                await asyncio.wait_for(revoked(), 1)
                assert not state.scrolling
                await notifier.routing.refresh()
                assert not state.scrolling
            finally:
                helper.cancel()
                await asyncio.gather(helper, return_exceptions=True)

                async def disconnected() -> None:
                    while notifier.writers:
                        await asyncio.sleep(0)

                await asyncio.wait_for(disconnected(), 1)

    asyncio.run(scenario())
