# rebase-bot-dispatch-pr-input

## Why

Issue #2446: `rebase-bot.yml`'s manual dispatch can only run the board-wide sweep
(`workflow_dispatch.inputs` exposes just `max_prs`), and when no open PR is behind, the sweep can
only ever answer `action=none`. That is why #1494's AC2 ("a behind PR is rebased onto main head")
was only PARTIALLY verified (run 42718138086 exercised only the no-op branch): the core behavior —
fetch → forward-merge `main` → structural gate → `--force-with-lease` push — has no on-demand
test vehicle. Rot in the rebase path is undetectable while the board happens to be current.

## What Changes

- `rebase-bot.yml` gains an optional `pr` `workflow_dispatch` input (no default). Unset = today's
  board-wide sweep, byte-identical behavior.
- `scripts/rebase_bot_sweep.py` gains `--pr <n>`: when set, the eligibility evaluation is
  restricted to that PR; every invariant still applies (daily cap, draft/base/owner checks,
  in-flight and claim coexistence, guard job, never-merges, force-with-lease to the PR's own head
  remote). A target that is not open against `main` answers `action=none` with a named reason.
- `mk/bots.mk`'s `rebase-bot-sweep` target forwards `TARGET_PR` to `--pr`; the workflow threads
  the input through the drain loop so every iteration stays aimed at the target.
- `AGENTS.md` documents the new input (unset = board-wide sweep) in the rebase-bot behavior text.

No behavior changes for the unset case, no permission or secrets changes.

## Impact

- Affected specs: none existing (new capability `rebase-bot-dispatch-pr-input`).
- Affected code: `.github/workflows/rebase-bot.yml`, `scripts/rebase_bot_sweep.py`,
  `mk/bots.mk`, `tests/test_rebase_bot_sweep.py`, `AGENTS.md`.
- After this lands, #1494's AC2 becomes re-verifiable: dispatch with `pr=<safe vehicle>` and
  observe `action=rebase` end-to-end (or a named, honest refusal).
