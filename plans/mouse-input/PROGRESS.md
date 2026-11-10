# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: not opened; publication remains held. Live installation authorized 2026-11-10.

## Current state

The requested visible global cursor behaviour is NOT complete. The user reports
terminal fallback shows the desired cursor; native Firefox scrolling does not.
The independent audit and a contained headful Wayland experiment reproduced
both failures: native scrolling never activates the shared renderer, and Firefox's
popup guard prevents the attempted CSS PNG from becoming the actual cursor.
Private state injection into the existing renderer produced actual themed up/down
cursor images over the still-active native browser popup, then restored the pointer.
Evidence: `~/.cache/dotfiles/gecko-wayland-cursor.v0fl6vrs/result.json`.

The repair now connects native autoscroll lifecycle to the existing renderer through
bounded presentation-only leases on the existing state socket. These peers cannot
enter routing or focus handlers. They have independent quotas and expire after
300ms, on disconnect or inactive logind UID state. Output is filtered by UID;
separate graphical sessions of the same UID are not isolated by this daemon.
The observer has no cursor images/styles or direction calculations. It hides the
fixed marker after daemon acceptance and restores it on cancellation or failure.
Acceptance is not a renderer acknowledgement; actual rendered verification is
required separately. Existing renderer code and physical input routing are unchanged.

The obsolete PNG compiler was removed. The full 118-test gate, Ruff, strict mypy,
Bash syntax and ShellCheck pass. A package was built and archive/import inspected.
An isolated Firefox proxy check preserves link/tab clicks, native scroll progress,
Escape cleanup and lost-ack restoration. Full candidate Wayland verification,
independent source review and live installation remain pending.

Native-default midscroll and its session services are installed and running at the
previous package. Native link/tab clicks and scrolling were confirmed by the user.
The old browser styling startup files were removed; the candidate state observer
has NOT yet been installed. A running browser can retain previously loaded code.
The 106-test/headless CSS results were never proof of actual pointer rendering.

## Reviews

Native Codex and independent security/concurrency reviews completed; all eleven
technical findings are resolved. The canonical Git-private work order preserves frozen
passes, original findings and dispositions. Resolve it with Engineering's
`workflow_ops.py --root CHECKOUT --workflow-run-id mouse-native review-path`.
The final documentation closeout uses that same work order; no second ledger or
published review artifact is introduced.

Automatic standards injection remains a separate issue per Tommy. Explicitly
loaded Python, Bash and C++ conventions govern this work; declarations restored
from the onboarding owner are preserved outside the mouse commits.

## Next action and limits

Run the full candidate through isolated actual Wayland cursor acceptance, review
the frozen source, then install the verified package and native lifecycle bridge.
Preserve the working link/tab routing. Browser startup activation and actual live
acceptance remain required before calling the visual issue fixed.

Root recovery: `/var/lib/dotfiles-mouse/recovery.XLA6WgJK`. Preserve unrelated work,
sessions and the withdrawn experiment. Publication is not authorized. Do not log
out, reboot, restart or hot-unload the live compositor.
