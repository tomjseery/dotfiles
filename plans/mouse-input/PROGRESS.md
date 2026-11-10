# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: not opened; publication and live deployment remain held.

## Current state

Routing preparation and seven causal review repairs are implemented. Current
committed tip `ee583dd` adds compositor observation barriers and event-driven
revocation. Installer/recovery cutover, native application defaults, thin public
wrappers and their regressions are being verified as the next coherent slice.
The obsolete pass-through manifests and installed-executable overlay wrapper are
removed from source; installed copies and restored runtime remain untouched.

Both native bridges passed actual contained compositor tests: target queries,
observation barriers, same-class root windows, A→B→A invalidation without querying
B, empty-area rejection and cleanup. KWin used a private virtual backend;
Hyprland nested inside it in a user namespace without physical input devices or
host seat/session sockets. A reproducible harness is being promoted beside the
bridges. This does not establish composed helper/daemon or physical acceptance.

Installer tests now exercise disposable homes, configs-only isolation, unchanged
repeat runs and recovery after a later settings failure. A private-root rehearsal
checks automatic recovery after a failed service restart and explicit recovery
after successful installation, using fake package/service boundaries. Real Arch
package rebuilding and system-interpreter archive inspection are separate checks.
The whole-source gate passes 76 tests, ruff and strict mypy; real native package
building and archive import inspection pass. Incremental review is pending.

## Reviews

Full frozen candidate `2ac49c8` received seven changes-requested findings in the
canonical Git-private work order. Causal repairs cover motion-frame ownership,
resynchronization, inactive peers, sandbox UID mapping, packaged imports, GUI
policy preservation and focus excursions. Reconcile the last two dispositions
with current evidence, then perform a fresh incremental review including installer
security. No clean watermark is claimed yet.

Automatic standards injection is a separate issue per Tommy. Explicitly loaded
Python, Bash and C++ conventions govern this work; declarations restored from the
onboarding owner are preserved and not silently published as mouse changes.

## Next Steps

Scope: approved source implementation through reviewable isolated verification.
Current slice: finish installer/package checks and reproducible bridge acceptance.
Remaining scope: final source gate, incremental review and remediation.
Done when: replacement source and concrete installation/recovery are reviewed and
verified; publication, live deployment and physical acceptance remain held.

Keep all source/runtime limitations explicit. Preserve the restored services,
withdrawn experiment, user changes and the separate standards-refactor owner.
