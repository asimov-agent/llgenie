# 2026-11-21 — a trigger-green merge sweep clears the verdict lane's own stale artifact row (issue #2991)

PR #2990 sat green-but-unmerged for two hours because the auto-merge sweep deferred on a red
`ci-verdict` row that the verdict lane replaces at every attempt. Measured from the sweep log
(run `44855608138`): at 02:23:28Z the sweep read PR #2990's head `8d4892e67…`, found
`ci-verdict` (failure, row `136684722878`) and posted a deferral; the fresh GREEN verdict row for
the same head landed at 02:23:38Z (row `136697078773`) — the sweep read the head ten seconds
before its own replacement row existed. The PR merged only after a head move re-fired the chain
(sweep `44865918139`, 04:24Z).

## What was verified

- The `merge` job in `auto-merge.yml` can only run under `workflow_run.event == 'pull_request'`
  and `workflow_run.conclusion == 'success'` at this head: the sweep is fired by a GREEN CI
  completion, so a red artifact of `ci-verdict.yml` left by an earlier verdict attempt is a stale
  artifact, not this head's verdict.
- The #2885 superseded-row collapse CANNOT clear this wedge: it collapses a red only when a newer
  CONCLUDED row of the same job name + workflow file already exists, and at read time the fresh
  green row does not exist yet.
- `scripts/auto_merge.py` names `VERDICT_ARTIFACT_FILE = "ci-verdict.yml"` (mirrors
  `ci_verdict.OUR_WORKFLOW_FILE`, #2221) and `failing_checks` gains `trigger_green`: a concluded-red
  row OF THAT WORKFLOW FILE clears with a named `stale verdict artifact (not a block)` note.
- The skip is keyed on the workflow FILE, never on a row name: the per-attempt `ci-verdict` JOB row
  of `ci.yml` still defers even with the trigger, a foreign red (issue-bot `implement`) still
  defers even with the trigger, and every sweep without a green trigger (recheck, `red-check`,
  `explain`) keeps the strict #1386 reading.
- 4 new sweep-level tests in `tests/test_auto_merge.py`: the wedge fixture (all-green CI attempt +
  stale `ci-verdict.yml` artifact red) merges under `trigger_green=True` and names the cleared row;
  the same head without the trigger defers naming the artifact; the `ci-verdict` JOB row of `ci.yml`
  defers; a foreign `implement` red defers.

## Key decisions

- The green-trigger proof is asserted by the workflow, not re-queried: `auto-merge.yml`'s merge step
  passes `TRIGGER_GREEN=1` because its job-level `if:` gate already proves the green completion;
  the flag is default-off everywhere else, so the strict consumers are untouched.
- Skipping the artifact is sound only for the verdict lane's OWN file; a green trigger never clears
  someone else's red — pinned by the foreign-red test.

## Current status

Fix implemented in `scripts/auto_merge.py`, wired through `mk/bots.mk` (`TRIGGER_GREEN=1`) and
`auto-merge.yml` (merge step); 4 tests green in the focused battery and in the full hermetic
battery. The companion defects measured the same night are issue #2992 (a stalled `in_progress`
job silences the chain) and issue #2993 / PR #2994 (the main-branch red repeat, fixed at the
verdict side).
