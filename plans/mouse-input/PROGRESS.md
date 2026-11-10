# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: https://github.com/tomjseery/dotfiles/pull/8 (draft for user code inspection).
Live installation authorized 2026-11-10; publication subsequently authorized.

## Current state

The installed fix is accepted. On 2026-11-10 the user confirmed "YEP WORKS now"
in response to the restart/visible-arrow/native-click acceptance check. This closes
the previously pending live Firefox cursor requirement. No further runtime changes
are needed for the accepted task.

Final production source is `44bb31d`. Installed engine, session reporter,
presentation module and browser observer hashes exactly match the final contained
Wayland acceptance. The live daemon and both session helpers restarted successfully.
An inactive presentation probe received acceptance from the real daemon, proving
that its actual session reporter, KWin PID correlation and renderer connection are
ready without activating the live cursor.

Final actual Wayland evidence uses the real native observer, session D-Bus reporter,
kernel socket PID correlation and unchanged existing KWin renderer. Native moving
up/down cursor pixels, scroll progress 0→1511, link opening, tab closing, Escape and
next-click stopping all pass. Dropping only the renderer restores the native marker
and pointer in 87.2ms. Fresh disabled-effect startup returns null readiness and
keeps the native circle visible. Evidence:
`~/.cache/dotfiles/gecko-final-full.0vx9wpuv/result.json` and
`~/.cache/dotfiles/gecko-final-absent.q1l69e2j/result.json`.

All 135 source tests, Ruff, strict mypy, Bash syntax and ShellCheck pass. The public
installer completed its real preparation, archive/import inspection, recovery and
root/user service stages. Installed AutoConfig startup passed its isolated profile
check, including native click semantics, scroll progress, closure revocation and
lost-ack restoration; this proxy test explicitly does not prove rendered pixels.
Its final advisory stop frame is optional: transport EOF is required revocation.

The failed CSS/PNG rendering path was removed. Native engines report bounded
presentation-only leases into one existing renderer. These peers cannot enter
routing or focus handlers. The existing trusted session helper supplies expiring
loaded-effect/PID observations; root matches a distinct same-UID socket peer.
No executable inspection or added daemon capability is used. Same-UID helper
impersonation remains within the existing local-user trust boundary, and separate
graphical sessions of the same UID remain outside the current setup's isolation.

Root recovery for this update: `/var/lib/dotfiles-mouse/recovery.wdowetCi`.
Earlier `/var/lib/dotfiles-mouse/recovery.XLA6WgJK` is retained too. No desktop
restart, effect hot-unload, profile rewrite or publication occurred.

## Reviews

Native Codex and independent security/correctness review approved final production
source `44bb31d`; all retained technical/visual findings are resolved. The canonical Git-private work order preserves frozen
passes, original findings and dispositions. Resolve it with Engineering's
`workflow_ops.py --root CHECKOUT --workflow-run-id mouse-native review-path`.
The final documentation closeout uses that same work order; no second ledger or
published review artifact is introduced.

Automatic standards injection remains a separate issue per Tommy. Explicitly
loaded Python, Bash and C++ conventions govern this work; declarations restored
from the onboarding owner are preserved outside the mouse commits.

## Next action and limits

Execution complete following the user's live acceptance. Keep the working setup
and retained recovery. No publication or further installation is requested.

Preserve unrelated work, sessions, prior recovery directories and the withdrawn
experiment. Publication is not authorized. Do not log out, reboot, restart or
hot-unload the live compositor.

## Code-organization follow-up

The user requested clearer plugin naming and the Python package cleanup during PR
inspection. `compositor-plugins/` replaces `target-bridges/`; all maintained path
references are updated. The existing routing implementation moved byte-for-byte
to `routing.py`; `__init__.py` explicitly re-exports its public API. All 135 tests,
Ruff, strict mypy, shell checks and a real Arch package/import check pass. KWin
builds at the new path. No live installation or compositor reload is part of this
source-only cleanup.

Installed Hyprland headers are now 0.57.2, while the unchanged plugin deliberately
requires ABI 0.57.1. Its rebuild is not claimed; this is an existing environment/
version mismatch, not caused by the directory move. Keep the ABI guard intact and
requalify Hyprland separately before installing against the newer compositor.

## Deferred C++ standards handoff

The user asked to consider C++23 explicit object parameters (deducing this) in a
later standards handoff. Owner: `cpp:mixins`; its examples currently use CRTP
self-casts. Assess replacing those examples where the supported toolchain and
composition semantics fit. Do not mechanically replace ordinary `static_cast`:
the casts in this PR's Wayland fixture convert C API `void*` data/results, and
explicit object parameters do not replace them. No C++ convention change was made.
