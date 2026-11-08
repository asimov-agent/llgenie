# 2026-11-08 — the tick arms auto-merge (issue #2182)

## The defect

`tick_board.sh` section B reported staleness and DIRTY but **not arm state**, and
nothing ever performed an arm. Measured at origin/main `3e2e64fa` across all 18
open PRs: `ARM armed=8 unarmed=10 armed-but-DIRTY(inert)=2`. Ten PRs had **no
`autoMergeRequest`**, so nothing merged them even when fully green. Two were
**armed AND DIRTY** — an armed DIRTY PR can never merge (DIRTY gets no CI run; the
merge queue never sees it), and the board could not tell "armed and waiting" from
"armed and impossible".

## What shipped

- **`agents/llgenie-planner/scripts/tick_board.sh`** — section B now requests
  `autoMergeRequest` and `reviewDecision` in its `gh pr list --json` field list
  (omitting them silently reads every PR as unarmed — a false measurement), and
  classifies each PR into one of four states: `armed`, `unarmed`,
  `armed-but-DIRTY` (the arm is **inert**), and `green+approved+unarmed`. It
  prints the `ARM armed=N unarmed=N armed-but-DIRTY(inert)=N` line and the rule
  that an inert arm is impossible, never handled.
- **`agents/llgenie-planner/scripts/arm_pr.sh`** — a single mechanical arm: read
  the PR, classify the four states, and arm **only** `green+approved+unarmed`
  (and only after its last push). It refuses a head with a live run or mid-rebase
  (#2069). The deciding proof is the **`autoMergeRequest` read back after the arm
  command** — the exit code is never proof, because `gh pr merge --auto` exits 0
  while arming nothing when the base is not the default branch (#964). An
  `armed-but-DIRTY` PR is reported to `llgenie-pr-merge-conflict` for a rebase and
  never counted as handled. Dry-run mode classifies without arming.
- **Prompt step** — the versioned orchestrator prompt already folds the ordered
  arming step (`4d` measure four states / `4e` arm only green+approved+unarmed
  then read back / `4f` never arm a red PR "so it merges later") from #2159; it is
  unchanged here (byte-identical to the live `jobs.json`).
- **Tests** — `tests/test_tick_board_arm.py` (the four-state classification incl.
  the known-armed-must-read-armed regression) and `tests/test_arm_pr.py` (the arm
  action, the #964 exit-0-but-unarmed refusal, and the #2069 live-run refusal),
  both hermetic with fakes.

## Safety / scope

The tick **arms**; it never merges by hand (owner rule, issue #1088). The
`REVIEW_REQUIRED`-on-every-PR identity constraint is #1088, not this issue. The
`ci-verdict` red flushing every PR is **#2156**, deliberately not fixed here
(that makes PRs green; this makes green PRs merge — neither substitutes for the
other). `auto-merge.yml`'s delivery defects are #2101.

## Verification

`tests/test_tick_board.py test_tick_board_arm.py test_arm_pr.py` — **16 passed**
hermetically. `make check-wiring` green (390 docs, 382 in CI). Versioned prompt
byte-identical to the live `jobs.json` at 14,045 b.
