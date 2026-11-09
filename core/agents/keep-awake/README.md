# Agent keep-awake

Prevents automatic idle actions while a Codex or Claude turn is active.
**An explicit Sleep request remains available**, including from a desktop power
menu. It requests only logind's `idle` inhibitor, never `sleep` or `shutdown`.
[systemd inhibitor documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd-inhibit.html)
explains the distinction. Hypridle honours systemd idle inhibitors by default;
KDE PowerDevil maps idle inhibition to its screen-settings policy, which also
implies its automatic-suspend policy.

From the repository root:

```sh
./install/agents.sh --dry-run
./install/agents.sh
```

The installer migrates links owned by the old `core/configs/agent-awake` package,
stows this module, reloads the user manager, enables the service and restarts it.
It refuses unrelated files/links. `--configs-only` installs links without touching
services; `install/core.sh` uses that mode to include agent configuration.
The executable and unit retain their existing `agent-awake` names.
Requirements: Bash, Python 3, GNU Stow and systemd.

```sh
agent-awake --check                     # active: exit 0; idle: exit 1
systemctl --user status agent-awake
systemd-inhibit --list
journalctl --user -u agent-awake
```

`activity.py` reads lifecycle records under `~/.codex/sessions` and
`~/.claude/projects`. Codex `task_started` opens an active turn; completion,
failure and abort records close it. Claude requests/tool-use open a turn;
end-turn and turn-finished records close it. Metadata/token-count writes alone
do not mark a session busy. No transcript contents or credentials are logged.
Reads are incremental in memory, with partial-line and replaced-file handling.

The default poll interval is five seconds (`AGENT_AWAKE_INTERVAL`). The legacy
`AGENT_AWAKE_QUIET_MINUTES` setting defaults to ten, but now only expires an
unfinished turn after that long without transcript updates, to recover from a
crash/missing completion. A completed turn releases without that grace period.
The old descendant-CPU heuristic and `AGENT_AWAKE_CHILD_TICKS` are retired:
background terminal processes are not evidence of an active agent turn.

Normal manual suspend is deliberately never overridden or forced by this
module. Other applications or system settings can independently prevent sleep.
