# Native middle-click and explicit fallback

## Authority and ownership

Tommy approved the fresh architecture assessment and implementation on 2026-11-09
("ok sounds good lets do it then"). The source-only checkpoint is superseded by Tommy's 2026-11-10 instruction to
make the live feature work. Live installation is now authorized and applied;
publication was later authorized for draft PR #8. Do not log out, reboot or restart the desktop. Preserve
unrelated preferences and sessions. On 2026-11-10 the user confirmed normal middle
clicks and native autoscroll work together, then requested the prior clean moving
arrow cursor instead of the browser's fixed circle. That visual requirement is
accepted by the user on 2026-11-10.
The withdrawn experiment and its uncommitted records remain untouched at
`/home/tommy/projects/dotfiles.worktrees/Fix-GenericMiddleClick`.

Canonical execution artifact: this file. The predecessor's mouse plan is
diagnostic history, not an active implementation or a second writer.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `origin/main`
`5625f551c40a1c86eae4a58a137d045fd460ae2c`. Draft PR:
https://github.com/tomjseery/dotfiles/pull/8. Merge is not requested.

## Decision and acceptance

Assessment complete: supported midscroll settings cannot express native-default
toggle routing. Keep upstream device handling/scroll calculation, patch its
explicit routing boundary at an immutable revision and build an Arch package.
Do not import or monkey-patch installed executables in production.

The daemon owns complete button sequences; target helpers supply evidence,
viewers only observe. Unknown, failed, ambiguous or stale targets stay native.
An active toggle belongs to its starting surface/session and one source device.
Fresh button decisions cannot let ticker work erase pending stop state. Retain
forwarded/consumed release ownership across cancellation and target changes.
Native tab-close, link/thumbnail opening and native autoscroll must coexist with
explicit opt-in fallback on KDE/Hyprland. No browser exception list.

## Delivery map

1. Routing engine and protocol patch, pinned source preparation and focused
   state/real-IPC regressions. Consumer: packaged midscroll, configured through
   native-default settings; bounded versioned target requests and explicit helper
   role. Expected 600–900 substantive lines; assess before expanding.
2. Desktop target helper, native application defaults, thin installer wrappers,
   disposable-root installation/recovery checks and documentation. Depends on
   the exact tested patch; same branch while publication held, with a fresh split
   assessment before exceeding the review budget. No live installation.
3. Independent review and isolated supported-desktop acceptance. Deployment and
   physical-input checks remain a separate user-authorized action.

## Standards and loading limits

Loaded: Workflow run/plan-artifacts, Engineering session/plans/branching and
validation; Python imports/modules/libraries/errors/domain-design/enums/style/
build/structure/testing; dotfiles root/core/install ownership. C++ domain design,
testing/style/libraries consulted for unchanged KWin participant. Bash published
source `61b38db` errors/testing/build/structure/domain-design consulted explicitly.
Python applicability verified by target hook; C++/G++ tier metadata incomplete;
Bash not claimed natively active. Repository has no Workflow v2 runtime/provider.
`tj status` advertised by Agent recover is unavailable in installed TJ CLI; no
ownership takeover or repair attempted. Existing onboarding owner owns tooling
reconciliation. This session uses explicit operation directories, not a claimed
native host retarget.

## Current evidence

- Main and withdrawn checkout changes are preserved, including concurrent work
  by their existing owners.
- Both restored services active; daemon/helper/config SHA-256 still match handoff.
- Independently reproduced passive-viewer timeout using actual Unix transport and
  peer UID checks, and ticker/query reset using deterministic in-memory inputs.
- Empty `focus ` report is stripped and ignored in deployed protocol, retaining
  the prior target. Installed runtime is not altered by these reproductions.
- Upstream candidate pin: `077d1b3016f4f4f86f608e06a6fc3c46430a9850`;
  source cache outside Git. State, pump, actual Unix transport, helper and recovery
  checks pass alongside lint and strict mypy. Real Arch packages build and pass
  extracted artifact-only system-interpreter import/CLI checks.
- Native focus bridges added separately from drawing; both compile against exact
  installed KWin 6.8.2/Hyprland 0.57.1. Both pass contained native interface probes;
  no plugin loaded in the live desktop. Stock Hyprland cannot
  supply authoritative recipient information, so geometry inference is excluded.
  These are version-bound compositor APIs; missing/incompatible bridges stay native.
- Split assessment: source/adapter/packaging/tests exceed the initial 900-line
  estimate. Keep runtime cutover atomic for review: splitting installation from its
  protocol/state tests or removing old routing before its replacement would expose
  broken behaviour. Preparation is locally committed separately; no published
  descendant stack is created under the explicit publication hold. Mechanical
  wrapper moves, lockfiles and bridge-build evidence are counted separately.

## Reviews

Technical review through `3a5c3b62f9f655a0e2361305394ee33ae514319e` is approved.
Native Codex and independent security/concurrency passes verified all eleven
technical findings and their causal repairs. The canonical Git-private work order
owns immutable pass identities, findings, dispositions and the current completion
watermark; resolve it with Engineering's `review-path` for run `mouse-native`.
Final documentation closeout uses the same work order.

The helper uses the already-installed managed `dbus-fast` API for a real awaited
D-Bus AddMatch barrier; stdlib has no D-Bus implementation, command monitor output
does not provide an equivalent reliable structured readiness contract. Dependency
assessment complete against official 5.2 API documentation; dependency is declared
in Python metadata/lock and Arch runtime package. External untyped wait coroutine
is isolated with a specific no-untyped-call annotation at that boundary.

Exact rollback source discovered read-only: upstream
`ac76b554cf6b279d646dee8336b45390d9db3597` matches all four installed midscroll
executables byte-for-byte. Its Arch PKGBUILD retained pkgver=1.14; the installed
baseline is 1.15-1. Build a separately verified recovery package from that revision
and preserve actual configuration/helper/unit state before any later authorized
installation. Only isolated recovery rehearsals have run; no live installation or recovery.

## Earlier source closeout

The routing/installer implementation was approved through `3a5c3b6`; its eleven
technical findings were resolved. Live installation was subsequently authorized
and performed. That earlier source approval did not prove the requested browser
cursor appearance. The canonical Git-private review work order remains the owner
of later passes; resolve it with Engineering's `review-path` for `mouse-native`.

## Completed visual acceptance

The user confirmed native link/tab clicks and scrolling work, then confirmed
"YEP WORKS now" on 2026-11-10 after the installed cursor fix. The visible cursor
requirement is accepted. Independent actual Wayland evidence reproduced the
missing native-state signal and the failure of CSS image cursors under Firefox's
popup guard. The existing global renderer successfully shows its actual themed
up/down cursor over native autoscroll when supplied with active state.

The selected repair adds generic presentation-only leases to the existing daemon
socket and a Gecko native-lifecycle adapter. It reuses the existing compositor
renderer; no browser cursor styles, image compiler or direction calculation remain.
Physical input routing and native scroll engines retain their current ownership.
The browser restores its fixed indicator when its lease cannot be maintained.

Final production source `44bb31d` passed real contained Wayland verification,
independent review and package/observer installation. All 135 source checks pass;
the installed files match the tested hashes and an inactive live readiness probe
passes. The user's subsequent live confirmation completes the acceptance condition.
See PROGRESS.md for the confirmation and retained recovery. The draft PR is open for inspection; merge is not requested.
