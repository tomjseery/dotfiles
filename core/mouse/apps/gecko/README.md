# Native autoscroll state bridge

`native-cursor.cfg` observes Gecko's actual browser-chrome autoscroll lifecycle
and reports a short-lived presentation lease to the existing midscroll state
socket. Midscroll merges it with fallback scrolling and notifies the same KWin
cursor renderer used by terminals. The browser adapter contains no cursor images,
direction calculations or cursor styles. Native scrolling, link opening and tab
closing remain owned by the browser.

After the daemon accepts a lease, the adapter makes the native fixed indicator
transparent. It restores its prior opacity on cancellation, socket failure or an
acknowledgement timeout. Acknowledgement establishes acceptance by the daemon;
it does not attest to actual cursor rendering. The adapter runs on KDE, where the
existing KWin renderer must be loaded. Other desktops retain the native indicator.
An explicitly supplied `MIDSCROLL_CURSOR_STATE_SOCKET` supports isolated testing.

The socket has separate, bounded presentation-only connections. These can report
advisory visual state but cannot enter input routing or focus handlers. Leases
expire after 300ms without renewal and are revoked on disconnect or inactive
logind user state. Rendering is filtered by UID. As with the existing daemon,
logind UID state does not isolate multiple graphical sessions of one account;
this setup targets the workstation's single graphical session.

Installation uses Mozilla's AutoConfig startup mechanism with root-owned files
under each discovered Gecko runtime. Its unsandboxed mode permits trusted local
browser-chrome code. Existing unrelated AutoConfig is refused. Configuration
activates at browser startup; profiles and sessions are preserved.

```sh
./core/mouse/install --cursor-only
```

This requires the corresponding midscroll package update; installing only the
observer against an old daemon leaves the native indicator intact. Full mouse
installation composes both. The retained recovery directory records exact startup
file snapshots in `native-cursor.json` before atomic writes.

```sh
uv run --directory core/mouse python tests/gecko_cursor_acceptance.py
uv run --directory core/mouse python tests/gecko_cursor_acceptance.py --installed
```

The disposable-profile check verifies native link/tab clicks, native scrolling,
presentation messages, popup opacity, cancellation and lost-ack recovery. Its
headless proxy does not prove rendered cursor appearance. Actual cursor acceptance
requires the separate contained Wayland experiment with the real KWin effect.
The observer was qualified with Firefox 159.0.1. Requalify after browser UI changes.

Chromium/Electron currently retain their native scrolling and cursor presentation.
