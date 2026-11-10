import json

import pytest

from midscroll_routing.presentation import (
    LEASE_SECONDS,
    RENDERER_LEASE_SECONDS,
    Presentation,
)


def frame(active: bool) -> str:
    return "presentation " + json.dumps({"version": 1, "active": active})


def test_renderer_reports_expire_and_revoke_on_disconnect() -> None:
    now = 0.0
    presentation = Presentation(lambda _: True, lambda: now)
    router = object()
    presentation.report_renderer(router, 'renderer {"version":1,"pid":101}')
    assert presentation.renderer_pid(router) == 101
    now = RENDERER_LEASE_SECONDS
    assert presentation.renderer_pid(router) is None
    presentation.report_renderer(router, 'renderer {"version":1,"pid":101}')
    presentation.disconnect(router)
    assert presentation.renderer_pid(router) is None
    presentation.report_renderer(router, 'renderer {"version":1,"pid":null}')
    assert presentation.renderer_pid(router) is None
    with pytest.raises(ValueError, match="Invalid renderer report"):
        presentation.report_renderer(router, 'renderer {"version":1,"pid":true}')


def test_presentation_expires_and_never_crosses_uid() -> None:
    now = 0.0
    presentation = Presentation(lambda _: True, lambda: now)
    peer = object()
    assert presentation.admit(peer, 1000)
    presentation.receive(peer, frame(True))
    assert presentation.active(1000)
    assert not presentation.active(1001)
    now = LEASE_SECONDS
    assert not presentation.active(1000)


def test_presentation_revokes_on_disconnect_or_session_loss() -> None:
    eligible = True
    presentation = Presentation(lambda _: eligible)
    first, second = object(), object()
    assert presentation.admit(first, 1000)
    assert presentation.admit(second, 1000)
    presentation.receive(first, frame(True))
    presentation.receive(second, frame(True))
    presentation.disconnect(first)
    assert presentation.active(1000)
    eligible = False
    assert not presentation.active(1000)
    eligible = True
    assert not presentation.active(1000)


@pytest.mark.parametrize(
    "message",
    [
        'routing {"version":1,"kind":"hello"}',
        "focus firefox",
        'presentation {"version":true,"active":true}',
        'presentation {"version":1,"active":1}',
        'presentation {"version":1,"active":true,"target":"kitty"}',
        "presentation []",
        "presentation {",
        "presentation " + " " * 256,
    ],
)
def test_presentation_rejects_other_authority_and_revokes(message: str) -> None:
    presentation = Presentation(lambda _: True)
    peer = object()
    assert presentation.admit(peer, 1000)
    presentation.receive(peer, frame(True))
    with pytest.raises(ValueError, match="Rejected presentation peer"):
        presentation.receive(peer, message)
    assert not presentation.active(1000)


def test_presentation_quotas_preserve_other_users_slots() -> None:
    presentation = Presentation(lambda _: True)
    for _ in range(4):
        assert presentation.admit(object(), 1000)
    assert not presentation.admit(object(), 1000)
    assert presentation.admit(object(), 1001)
    assert not Presentation(lambda _: False).admit(object(), 1000)
