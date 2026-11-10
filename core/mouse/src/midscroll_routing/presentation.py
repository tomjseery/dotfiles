"""Advisory native-scroll leases, independent of physical input ownership."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass

LEASE_SECONDS = 0.3
RENDERER_LEASE_SECONDS = 1.0
MAX_PEERS = 8
MAX_PEERS_PER_UID = 4
ACCEPTED = b'presentation {"version":1,"accepted":true}\n'


@dataclass(frozen=True, slots=True)
class Lease:
    uid: int
    deadline: float


class Presentation:
    """Each native engine can renew only its own short-lived visual state."""

    def __init__(
        self,
        eligible: Callable[[int], bool],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.eligible = eligible
        self.clock = clock
        self.peers: dict[object, int] = {}
        self.leases: dict[object, Lease] = {}
        self.renderers: dict[object, tuple[int | None, float]] = {}

    def report_renderer(self, router: object, line: str) -> None:
        """Caller admits only the existing registered routing authority."""
        if not line.startswith("renderer ") or len(line) > 256:
            raise ValueError("Invalid renderer frame")
        payload = json.loads(line[9:])
        if (
            not isinstance(payload, dict)
            or set(payload) != {"version", "pid"}
            or type(payload["version"]) is not int
            or payload["version"] != 1
            or (
                payload["pid"] is not None
                and (
                    type(payload["pid"]) is not int
                    or not 0 < payload["pid"] <= 0xFFFFFFFF
                )
            )
        ):
            raise ValueError("Invalid renderer report")
        self.renderers[router] = (payload["pid"], self.clock() + RENDERER_LEASE_SECONDS)

    def renderer_pid(self, router: object) -> int | None:
        report = self.renderers.get(router)
        if report is None:
            return None
        pid, deadline = report
        if self.clock() >= deadline:
            self.renderers.pop(router, None)
            return None
        return pid

    def admit(self, peer: object, uid: int) -> bool:
        if (
            not self.eligible(uid)
            or len(self.peers) >= MAX_PEERS
            or sum(owner == uid for owner in self.peers.values()) >= MAX_PEERS_PER_UID
        ):
            return False
        self.peers[peer] = uid
        return True

    def disconnect(self, peer: object) -> None:
        self.peers.pop(peer, None)
        self.leases.pop(peer, None)
        self.renderers.pop(peer, None)

    def receive(self, peer: object, line: str) -> None:
        """Accept only presentation frames; malformed input revokes the peer."""
        try:
            if not line.startswith("presentation ") or len(line) > 256:
                raise ValueError("Invalid presentation frame")
            payload = json.loads(line[13:])
            if (
                not isinstance(payload, dict)
                or set(payload) != {"version", "active"}
                or type(payload["version"]) is not int
                or payload["version"] != 1
                or type(payload["active"]) is not bool
            ):
                raise ValueError("Invalid presentation fields")
            uid = self.peers[peer]
            if not self.eligible(uid):
                raise ValueError("Presentation session is inactive")
        except (ValueError, KeyError) as error:
            self.disconnect(peer)
            raise ValueError("Rejected presentation peer") from error
        if payload["active"]:
            self.leases[peer] = Lease(uid, self.clock() + LEASE_SECONDS)
        else:
            self.leases.pop(peer, None)

    def active(self, uid: int) -> bool:
        now = self.clock()
        for peer, lease in list(self.leases.items()):
            if now >= lease.deadline or not self.eligible(lease.uid):
                self.leases.pop(peer, None)
        return any(lease.uid == uid for lease in self.leases.values())
