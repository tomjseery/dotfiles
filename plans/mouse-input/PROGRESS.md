# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: not opened; publication and live deployment remain held.

## Current state

Authorized source implementation and isolated verification are complete.
Technical source review is approved through `3a5c3b62f9f655a0e2361305394ee33ae514319e`.
The branch contains pinned native-default routing, typed session/gesture handling,
actual compositor target bridges, native application defaults, thin public
installer entry points and retained package/file recovery. Obsolete pass-through
manifests and the installed-executable overlay wrapper are removed from source.
Installed copies and the restored runtime remain untouched.

The actual public `core/mouse/install --prepare` completes with 80 tests, ruff,
strict mypy, both bridge builds, real Arch package/import inspection and a recovery
archive matching installed package files. Bash syntax, ShellCheck and shfmt pass.
Installer regressions cover private homes/locks, configs-only isolation, repeat
runs, relocated checkouts, overlapping invocations, user-stage failure, and both
automatic and explicit private-root recovery with synthetic package/service I/O.

Both native bridges pass the committed contained compositor harness: observation
readiness, actual same-class root targets, A→B→A without querying B, new generations,
empty-area rejection and final invalidation. KWin uses a virtual backend;
Hyprland nests inside it without physical input nodes or host seat/session sockets.
Generated results are ignored under the harness's artifacts directory.

## Reviews

Native Codex and independent security/concurrency reviews completed; all eleven
findings are resolved. The canonical Git-private work order preserves frozen
passes, original findings and dispositions. Resolve it with Engineering's
`workflow_ops.py --root CHECKOUT --workflow-run-id mouse-native review-path`.
The final documentation closeout uses that same work order; no second ledger or
published review artifact is introduced.

Automatic standards injection remains a separate issue per Tommy. Explicitly
loaded Python, Bash and C++ conventions govern this work; declarations restored
from the onboarding owner are preserved outside the mouse commits.

## Next action and limits

The authorized source acceptance condition is met. Publication, live installation,
desktop/service activation and physical acceptance remain held under the plan's
recorded scope. No deployment is implied by a source commit or review approval.

A later authorized deployment must verify complete helper/daemon/application
composition and physical KDE/Hyprland behaviour: native tab closing, link opening,
native autoscroll, fallback start/stop, eligibility transitions and multiple
input devices. The bridge snapshot and IPC timing limits remain explicit in the
owning README. Source tests do not establish these deployment claims.

Preserve restored services, the withdrawn experiment, unrelated user changes and
the separate standards-refactor owner. Retain verified packages and recovery
artifacts until deployment acceptance.
