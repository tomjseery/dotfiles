# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: not opened; publication remains held. Live installation authorized 2026-11-10.

## Current state

The requested visible global cursor behaviour is NOT complete. The user reports
terminal fallback shows the desired cursor; native Firefox scrolling does not.
Implementation changes are frozen for an independent read-only root-cause audit.

Native-default midscroll and its session services are installed and running.
Normal native link/tab middle-click and scrolling were confirmed by the user.
The attempted AutoConfig/CSS workaround was installed, then its two startup files
were restored/removed using the retained native-cursor.json recovery. A running
browser may retain already-loaded code until restart. Do not reapply that workaround.

The 106-test gate and headless real-browser checks established input semantics,
configuration handling and computed CSS. They did NOT establish actual compositor
cursor rendering. Earlier statements treating those checks as visible cursor
acceptance were incorrect.

Confirmed shared-renderer break: installed midscroll broadcasts its fallback
State.scrolling only. Native browser input is passed through, so it never sets
that flag. The loaded KWin effect reads only that flag; it has no native browser
scroll-state input. Its installed library hash matches the cached build.

Independent fresh review completed. Exact Firefox 159.0.1 source opens a non-tooltip
XUL autoscroll panel; the popup manager disables custom image cursors by default
and GTK then uses the ordinary cursor. Making that panel transparent leaves the
guard active. The source default is verified and installed autoscroll JavaScript
matches the release source byte-for-byte; effective LIVE preference/widget state
has not been measured. Do not present that live value as observed.

This explains why computed PNG CSS and headless scrolling tests could pass without
proving a visible cursor. Preserve the browser security preference. The next
measurement is an isolated actual Wayland run that reads the effective preference
and observes the emitted/rendered cursor during native autoscroll. No further
implementation or live state changes were made in the independent audit.

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

Complete the independent causal report with exact source evidence and separate
observed facts from unverified hypotheses. Choose the next discriminating rendered
cursor measurement before any further implementation. The target remains one
shared global renderer with normal native click behaviour; browser-specific cursor
styling has been rejected by the user.

Root recovery: `/var/lib/dotfiles-mouse/recovery.XLA6WgJK`. Preserve unrelated work,
sessions and the withdrawn experiment. Publication is not authorized. Do not log
out, reboot, restart or hot-unload the live compositor.
