# Agent keep-awake refactor

User authorised changing agent-awake so manual Sleep works, organising agent
configuration under an agents/keep-awake area, updating dotfiles and applying
the corrected service. Keep this personal behaviour under core/agents/keep-awake.
Preserve the legacy executable/service names. User subsequently clarified that
an idle agent must release inhibition promptly: replace the recent-file/CPU
heuristics with explicit transcript turn lifecycle detection.
Do not actually suspend, restart the desktop or change theme/appearance here.

Branch Refactor/AgentKeepAwake, parent Feature/LoginTheme at 19f473f: local
organisation/install helpers are a dependency. No remote publication requested.
Existing KDE shortcut/panel state and untracked kde/ are unrelated live changes;
preserve and exclude them. Standalone plan-execution fallback, no workflow runtime.
Implementation/review lane L4; bounded code and installer checks. No model switch
claimed. No separate session requested or launched.

## Delivery

One focused local refactor: relocate module, distinguish idle inhibition from
explicit suspend, migrate only owned legacy links, separate agents installer,
regression tests, live service restart/inhibitor verification, local commit.

## Initial investigation

Confirmed active systemd inhibitor is agent-awake with idle:sleep in block mode;
CanSuspend reports yes. Native hypridle honours idle-only inhibitors by default.
KDE maps idle inhibition to ChangeScreenSettings, which implies InterruptSession
for automatic suspend. Move-only commit: 1ac7f2f. Implement explicit turn markers
and incremental reads, then apply and verify. Tests must cover manual
sleep not inhibited, active/quiet activity transitions and legacy-link migration
without overwriting unrelated user files. No real suspend test.

## Implementation checkpoint

Module moved to core/agents/keep-awake; executable/unit names retained.
install/agents.sh preflights owned paths, migrates only legacy links, stows the
module and enables/restarts its user service. Core includes links via the
configs-only path. The Python activity detector replaces the ten-minute busy
heuristic and descendant CPU guesses; reads task lifecycle markers incrementally
and expires only stale unfinished turns. Poll every five seconds, idle-only
logind inhibition with no password prompts. Component README owns details.

All 13 repository tests pass, including lifecycle completion with fresh metadata,
partial and rewritten transcripts, stale turn recovery, Claude completion,
inhibitor release and absence of sleep inhibition, fresh/repeated installs,
legacy-link migration, dry-run preservation and unrelated-file refusal. Bash
syntax checks pending final invocation; no actual suspend has been attempted.

## Completed validation and delivery

Live installation migrated both owned legacy links and installed the helper,
reloaded the user manager, enabled/restarted agent-awake.service successfully.
MainPID 159518 is the new Python daemon. Old sleep/idle blocker PID 4394 was
removed by the service restart. Native systemd-inhibit reports agent-awake's
WHAT as idle only; NetworkManager/UPower/hypridle retain their unrelated sleep
**delay** inhibitors. Status check reports active during this turn. Manual
suspend was deliberately not invoked; verification establishes removal of this
module's blocker, not hardware suspend/resume success.

Source/manual review found and resolved absolute-link migration handling,
transcript rewrite detection and Stow metadata exclusions. A local
.stow-local-ignore excludes module documentation and Python caches. All 13
repository tests pass after the final code change; wrapper/installer Bash syntax
and git diff --check pass. Shellcheck is unavailable. No independent reviewer
result is claimed. Root AGENTS/CLAUDE symlink remains unchanged.

The behaviour/docs/install change is ready for its local commit following the
move-only commit 1ac7f2f. No push requested. Unrelated KDE shortcut and panel edits,
and old untracked kde/, remain untouched and excluded. End-4 visual/fork choices
remain a separate local trial and are not adopted into this repository.
