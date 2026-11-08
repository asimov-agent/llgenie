# Make the orchestrator tick arm auto-merge (issue #2182)

## Why

A green PR needs an `autoMergeRequest` to merge; nothing ever created one.
Measured 2026-11-08 at origin/main `3e2e64fa` across all 18 open PRs:
`ARM armed=8 unarmed=10 armed-but-DIRTY(inert)=2`. Ten PRs had no arm, so
nothing merged them even when fully green. Two were armed **and** DIRTY — an
armed DIRTY PR can never merge (DIRTY gets no CI run; the merge queue never
sees it), and `tick_board.sh` section B did not measure arm state at all, so the
board could not tell "armed and waiting" from "armed and impossible". The SOUL
rule "arm when done, then read autoMergeRequest back" had no procedure behind it.

## The change

1. **`tick_board.sh` section B measures arm state.** Request
   `autoMergeRequest` and `reviewDecision` in the `gh pr list --json` field list
   (omitting them silently reads every PR unarmed — a false measurement) and
   classify each PR into four states: `armed`, `unarmed`, `armed-but-DIRTY`
   (the arm is **inert**), `green+approved+unarmed`. Print
   `ARM armed=N unarmed=N armed-but-DIRTY(inert)=N`.

2. **`arm_pr.sh` — one mechanical arm.** Read the PR, classify the four states,
   and arm **only** `green+approved+unarmed` (after its last push). Refuse a
   head with a live run or mid-rebase (#2069). The proof is the
   **`autoMergeRequest` read back after `gh pr merge --auto`** — the exit code
   is never proof (#964: `gh pr merge --auto` exits 0 while arming nothing when
   the base is not the default branch). An `armed-but-DIRTY` PR is routed to
   `llgenie-pr-merge-conflict` for a rebase and never counted as handled.

3. **The prompt step is already versioned.** Step 4d/4e/4f of the versioned
   orchestrator prompt carries the ordered arming step from #2159; this change
   leaves it byte-identical to the live `jobs.json`.

4. **Hermetic tests.** `tests/test_tick_board_arm.py` and `tests/test_arm_pr.py`
   cover the four states, the known-armed-must-read-armed regression, the #964
   exit-0-but-unarmed refusal, and the #2069 live-run refusal.
