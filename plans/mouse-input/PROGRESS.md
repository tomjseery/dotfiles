# Mouse routing execution

Plan: [PLAN.md](PLAN.md)

Owner: this conversation; implementation authorized 2026-11-09.
Checkout: `/home/tommy/projects/dotfiles/.worktrees/Fix-MouseGestureOwnership`.
Branch: `Fix/MouseGestureOwnership`; base `5625f551c40a1c86eae4a58a137d045fd460ae2c`.
PR: not opened; publication and live deployment remain held.

## Current state

Preparation slice implemented: native-default patch at immutable upstream
`077d1b3016f4f4f86f608e06a6fc3c46430a9850`, typed routing/helper package,
read-only native KWin/Hyprland bridges and reproducible Arch package preparation.
Existing installer and live runtime are unchanged. No bridge loaded.
27 tests, ruff and strict mypy pass. Both bridge libraries compile. Arch package
build succeeds without installation. Bash syntax, ShellCheck and shfmt pass for
the new focused check command. Logs under shared Git `agent-workflow/runs/mouse-native`.

## Reviews

Preparation candidate not yet reviewed. Installation, recovery and real isolated
compositor acceptance remain unfinished. Do not deploy from this checkpoint.

## Next Steps

Scope: approved implementation through reviewable tested source, without publication/deployment.
Current slice: review preparation candidate, then implement installer/recovery and isolated acceptance.
Remaining scope: package inspection, source review, installer checks, composed desktop acceptance.
Done when: replacement source and a rehearsed installation/recovery path are reviewed and verified.

Review the committed preparation candidate before wiring installers. Preserve the
restored services, withdrawn experiment, user changes and standards-refactor owner.
