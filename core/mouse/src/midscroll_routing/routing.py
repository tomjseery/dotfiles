"""Gesture ownership and versioned target IPC, shipped inside patched midscroll."""

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol

log = logging.getLogger(__name__)
QUERY_TIMEOUT = 0.2
LEASE_SECONDS = 0.3


class ScrollState(Protocol):
    def reset(self) -> None: ...
    def begin_toggle(self) -> None: ...


class Owner(Enum):
    NATIVE = auto()
    START = auto()
    STOP = auto()


@dataclass(frozen=True, slots=True)
class Target:
    session: str
    surface: str
    app: str

    @classmethod
    def parse(cls, payload: object) -> Target | None:
        if payload is None:
            return None
        if not isinstance(payload, dict) or set(payload) != {
            "session",
            "surface",
            "app",
        }:
            raise ValueError("Invalid target fields")
        if any(
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or not value.isprintable()
            for value in payload.values()
        ):
            raise ValueError("Invalid target identity")
        return cls(payload["session"], payload["surface"], payload["app"].casefold())


@dataclass(eq=False, slots=True)
class Gesture:
    state: ScrollState
    owners: dict[int, Owner] = field(default_factory=dict)


@dataclass(slots=True)
class Lease:
    writer: asyncio.StreamWriter
    target: Target
    deadline: float


class Routing:
    """One seat's fallback; physical devices retain independent release ledgers."""

    def __init__(
        self,
        fallback_apps: frozenset[str],
        middle_button: int,
        eligible: Callable[[asyncio.StreamWriter], bool],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.fallback_apps = fallback_apps
        self.middle_button = middle_button
        self.eligible = eligible
        self.clock = clock
        self.routers: set[asyncio.StreamWriter] = set()
        self.pending: dict[
            str, tuple[asyncio.StreamWriter, asyncio.Future[Target | None]]
        ] = {}
        self.active: Gesture | None = None
        self.lease: Lease | None = None
        self.paused = False
        self.lock = asyncio.Lock()
        self.generation = 0

    def authorities(self) -> list[asyncio.StreamWriter]:
        return [peer for peer in self.routers if self.eligible(peer)]

    def stop(self) -> None:
        if self.active is not None:
            self.active.state.reset()
        self.active = None
        self.lease = None

    def valid(self) -> bool:
        lease = self.lease
        return (
            lease is not None
            and lease.writer in self.routers
            and self.eligible(lease.writer)
            and len(self.authorities()) == 1
            and self.clock() < lease.deadline
        )

    def on_clock(self) -> None:
        if not self.paused and not self.valid():
            self.stop()

    def can_scroll(self, gesture: Gesture) -> bool:
        return not self.paused and self.active is gesture and self.valid()

    def disconnect(self, writer: asyncio.StreamWriter) -> None:
        if writer in self.routers:
            self.generation += 1
        self.routers.discard(writer)
        for peer, future in self.pending.values():
            if peer is writer and not future.done():
                future.set_result(None)
        if self.lease is not None and self.lease.writer is writer:
            self.stop()

    def receive(self, writer: asyncio.StreamWriter, text: str) -> bool:
        if not text.startswith("routing "):
            return False
        try:
            payload = json.loads(text[8:])
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("Unsupported routing message")
            kind = payload.get("kind")
            if kind == "hello":
                self.routers.add(writer)
                # Inactive session peers remain registered for later activation.
                if self.eligible(writer):
                    self.generation += 1
                if len(self.authorities()) != 1:
                    self.stop()
            elif kind == "reply":
                token = payload.get("token")
                if isinstance(token, str) and token in self.pending:
                    peer, future = self.pending[token]
                    if peer is writer and not future.done():
                        future.set_result(Target.parse(payload.get("target")))
            elif kind == "target":
                Target.parse(payload.get("target"))
                if writer in self.routers and self.eligible(writer):
                    self.generation += 1
                    self.stop()
                    for peer, future in self.pending.values():
                        if peer is writer and not future.done():
                            future.set_result(None)
                # Unsolicited reports can revoke but never extend a lease.
            else:
                raise ValueError("Unknown routing message")
        except (ValueError, TypeError) as error:
            log.warning("Invalid routing peer: %s", error)
            self.disconnect(writer)
        return True

    async def query(self) -> Lease | None:
        peers = self.authorities()
        if len(peers) != 1:
            return None
        writer = peers[0]
        if writer.transport.get_write_buffer_size() > 4096:
            return None
        token = secrets.token_hex(8)
        generation = self.generation
        future: asyncio.Future[Target | None] = (
            asyncio.get_running_loop().create_future()
        )
        self.pending[token] = (writer, future)
        try:
            request = {"version": 1, "kind": "query", "token": token}
            writer.write(("routing " + json.dumps(request) + "\n").encode())
            target = await asyncio.wait_for(future, QUERY_TIMEOUT)
            if (
                target is None
                or target.app not in self.fallback_apps
                or writer not in self.routers
                or not self.eligible(writer)
                or len(self.authorities()) != 1
                or generation != self.generation
            ):
                return None
            return Lease(writer, target, self.clock() + LEASE_SECONDS)
        except (TimeoutError, OSError) as error:
            log.debug("Target query unavailable: %s", error)
            return None
        finally:
            self.pending.pop(token, None)

    async def button(
        self, gesture: Gesture, code: int, value: int, *, resolved_motion: bool = True
    ) -> bool:
        """Return whether to consume; a down decision owns its matching up."""
        if value == 0:
            owner = gesture.owners.pop(code, Owner.STOP)
            if owner is Owner.START and self.active is gesture:
                if self.valid():
                    gesture.state.begin_toggle()
                else:
                    self.stop()
            return owner is not Owner.NATIVE
        if value != 1 or code in gesture.owners:
            return gesture.owners.get(code, Owner.NATIVE) is not Owner.NATIVE
        async with self.lock:
            self.on_clock()
            if not resolved_motion:
                self.stop()
                gesture.owners[code] = Owner.NATIVE
                return False
            if code != self.middle_button and self.active is None:
                gesture.owners[code] = Owner.NATIVE
                return False
            self.paused = True
            try:
                lease = await self.query()
                previous = self.lease
                same_target = (
                    self.active is not None
                    and lease is not None
                    and previous is not None
                    and lease.writer is previous.writer
                    and lease.target == previous.target
                )
                self.stop()
                owner = Owner.NATIVE
                if same_target:
                    owner = Owner.STOP
                elif lease is not None and code == self.middle_button:
                    owner = Owner.START
                    self.active, self.lease = gesture, lease
                gesture.owners[code] = owner
                return owner is not Owner.NATIVE
            finally:
                self.paused = False

    async def refresh(self) -> None:
        """Renew through a correlated query; observations alone cannot grant."""
        async with self.lock:
            active, previous = self.active, self.lease
            if active is None or previous is None:
                return
            lease = await self.query()
            if self.active is not active:
                return
            if (
                lease is None
                or lease.writer is not previous.writer
                or lease.target != previous.target
            ):
                self.stop()
            else:
                self.lease = lease

    def release_device(self, gesture: Gesture) -> None:
        if self.active is gesture:
            self.stop()
        gesture.owners.clear()

    def resync(self, gesture: Gesture, forwarded: set[int]) -> None:
        """Retain releases owed to the application after upstream resync."""
        if self.active is gesture:
            self.stop()
        gesture.owners = dict.fromkeys(forwarded, Owner.NATIVE)
