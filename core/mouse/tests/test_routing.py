import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pytest

import midscroll_routing as routing


@dataclass
class State:
    scrolling: bool = False

    def reset(self) -> None:
        self.scrolling = False

    def begin_toggle(self) -> None:
        self.scrolling = True


TARGET = {"session": "kde-session", "surface": "window-1", "app": "kitty"}


@dataclass
class Transport:
    pending: int = 0

    def get_write_buffer_size(self) -> int:
        return self.pending


class Peer:
    def __init__(self, broker: routing.Routing) -> None:
        self.broker = broker
        self.transport = Transport()
        self.target: object = TARGET
        self.silent = False
        self.requests: list[str] = []
        self.on_query: Callable[[], None] = lambda: None

    @property
    def writer(self) -> asyncio.StreamWriter:
        # This is the bounded external transport adapter; production uses StreamWriter.
        return cast(asyncio.StreamWriter, self)

    def write(self, data: bytes) -> None:
        request = json.loads(data.decode()[8:])
        self.requests.append(request["token"])
        self.on_query()
        if not self.silent:
            asyncio.get_running_loop().call_soon(
                self.broker.receive,
                self.writer,
                "routing "
                + json.dumps(
                    {
                        "version": 1,
                        "kind": "reply",
                        "token": request["token"],
                        "target": self.target,
                    }
                ),
            )


def setup() -> tuple[routing.Routing, Peer, State, routing.Gesture, list[float]]:
    now = [0.0]
    broker = routing.Routing(frozenset({"kitty"}), 274, lambda _: True, lambda: now[0])
    peer = Peer(broker)
    broker.receive(peer.writer, 'routing {"version":1,"kind":"hello"}')
    state = State()
    return broker, peer, state, routing.Gesture(state), now


def test_native_and_fallback_complete_sequences() -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, _ = setup()
        for target in [None, dict(TARGET, app="future-browser"), TARGET]:
            peer.target = target
            consumed = target == TARGET
            assert await broker.button(gesture, 274, 1) is consumed
            assert await broker.button(gesture, 274, 0) is consumed
            assert state.scrolling is consumed
            broker.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("button", [272, 273, 274])
def test_stop_stays_stop_while_clock_fires_during_query(button: int) -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, now = setup()
        await broker.button(gesture, 274, 1)
        await broker.button(gesture, 274, 0)
        assert state.scrolling

        def tick() -> None:
            now[0] = 10
            broker.on_clock()
            assert state.scrolling
            assert not broker.can_scroll(gesture)

        peer.on_query = tick
        assert await broker.button(gesture, button, 1)
        assert await broker.button(gesture, button, 0)
        assert not state.scrolling

    asyncio.run(scenario())


def test_changed_surface_same_class_cancels_previous_toggle() -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, _ = setup()
        await broker.button(gesture, 274, 1)
        await broker.button(gesture, 274, 0)
        peer.target = dict(TARGET, surface="window-2")
        assert not await broker.button(gesture, 272, 1)
        assert not await broker.button(gesture, 272, 0)
        assert not state.scrolling

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["disconnect", "expiry", "change", "duplicate"])
def test_consumed_press_retains_release_after_revocation(failure: str) -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, now = setup()
        assert await broker.button(gesture, 274, 1)
        match failure:
            case "disconnect":
                broker.disconnect(peer.writer)
            case "expiry":
                now[0] = 1
                broker.on_clock()
            case "change":
                broker.receive(
                    peer.writer, 'routing {"version":1,"kind":"target","target":null}'
                )
            case "duplicate":
                broker.receive(
                    Peer(broker).writer, 'routing {"version":1,"kind":"hello"}'
                )
        assert await broker.button(gesture, 274, 0)
        assert not state.scrolling

    asyncio.run(scenario())


def test_forwarded_press_retains_release_after_new_permission() -> None:
    async def scenario() -> None:
        broker, peer, _, gesture, _ = setup()
        peer.target = None
        assert not await broker.button(gesture, 274, 1)
        peer.target = TARGET
        other = routing.Gesture(State())
        await broker.button(other, 274, 1)
        assert not await broker.button(gesture, 274, 0)

    asyncio.run(scenario())


def test_passive_viewer_never_receives_a_query() -> None:
    async def scenario() -> None:
        broker, _, _, gesture, _ = setup()
        viewer = Peer(broker)
        assert not broker.receive(viewer.writer, "focus kitty")
        assert await broker.button(gesture, 274, 1)
        assert not viewer.requests

    asyncio.run(scenario())


def test_renewal_and_changed_target_stop_without_reviving() -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, now = setup()
        await broker.button(gesture, 274, 1)
        await broker.button(gesture, 274, 0)
        for instant in [0.1, 0.3, 0.5]:
            now[0] = instant
            await broker.refresh()
            broker.on_clock()
            assert state.scrolling
        peer.target = None
        await broker.refresh()
        assert not state.scrolling
        peer.target = TARGET
        await broker.refresh()
        assert not state.scrolling

    asyncio.run(scenario())


def test_second_device_stops_seat_toggle_and_keeps_its_release() -> None:
    async def scenario() -> None:
        broker, _, state, gesture, _ = setup()
        await broker.button(gesture, 274, 1)
        await broker.button(gesture, 274, 0)
        other = routing.Gesture(State())
        assert await broker.button(other, 274, 1)
        assert not state.scrolling
        broker.release_device(gesture)
        assert await broker.button(other, 274, 0)

    asyncio.run(scenario())


def test_missing_slow_backlogged_helpers_and_late_replies_stay_native() -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, _ = setup()
        peer.silent = True
        assert not await broker.button(gesture, 274, 1)
        assert not await broker.button(gesture, 274, 0)
        token = peer.requests[-1]
        broker.receive(
            peer.writer,
            "routing "
            + json.dumps(
                {
                    "version": 1,
                    "kind": "reply",
                    "token": token,
                    "target": TARGET,
                }
            ),
        )
        assert not state.scrolling
        peer.transport.pending = 65536
        assert not await broker.button(gesture, 274, 1)
        assert not await broker.button(gesture, 274, 0)
        broker.disconnect(peer.writer)
        assert not await broker.button(gesture, 274, 1)
        assert not await broker.button(gesture, 274, 0)

    asyncio.run(scenario())


def test_inactive_authority_cannot_veto_active_session() -> None:
    async def scenario() -> None:
        broker, old, _, gesture, _ = setup()
        current = Peer(broker)
        broker.eligible = lambda peer: peer is current.writer
        broker.receive(current.writer, 'routing {"version":1,"kind":"hello"}')
        assert len(broker.routers) == 2
        assert await broker.button(gesture, 274, 1)
        assert not old.requests

    asyncio.run(scenario())


def test_focus_invalidation_during_query_cannot_grant_or_restart() -> None:
    async def scenario() -> None:
        broker, peer, state, gesture, _ = setup()

        def change() -> None:
            broker.receive(
                peer.writer, 'routing {"version":1,"kind":"target","target":null}'
            )

        peer.on_query = change
        assert not await broker.button(gesture, 274, 1)
        assert not await broker.button(gesture, 274, 0)
        assert not bool(state.scrolling)
        peer.on_query = lambda: None
        assert await broker.button(gesture, 274, 1)
        assert await broker.button(gesture, 274, 0)
        assert bool(state.scrolling)
        change()
        assert not state.scrolling
        await broker.refresh()
        assert not state.scrolling

    asyncio.run(scenario())


def test_resync_preserves_only_forwarded_button_releases() -> None:
    async def scenario() -> None:
        broker, _, _, gesture, _ = setup()
        assert not await broker.button(gesture, 272, 1)
        assert await broker.button(gesture, 274, 1)
        broker.resync(gesture, {272})
        assert not await broker.button(gesture, 272, 0)
        assert await broker.button(gesture, 274, 0)

    asyncio.run(scenario())
