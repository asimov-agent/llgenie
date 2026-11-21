# Make the verdict lane post `neutral` at a green default-branch run (issue #2993)

## Why

The main branch repeatedly shows red `ci-verdict` runs and red `ci-verdict` rows at each new `main` tip while main's CI is green. Measured at main `a4afb185e23900412a5a7a337069daf08324e214`: verdict run `44823923197` judged main's own CI push run `44819931621` (completed `success` at 2026-11-20T21:50:58Z) and posted artifact row `136591838065` with `conclusion=failure` at `21:51:40Z`. The judged jobs were all green; the verdict was forced red only by `unjudged_reds` — the `implement` job failures of issue-bot runs `44822618375` / `44822619990` (rows `136589328437` / `136589325345`) that `workflow_run` bot lanes post directly at the default-branch head. The #2116 forcing (`GREEN judged verdict + unjudged reds => red`) exists because a PR head with an unjudged red is unmergeable — but a `main` commit gates no merge at all: `scripts/auto_merge.py` merges PR heads, never main. Every completed main push re-triggers the verdict, which re-posts a red row at the new tip while any bot row at the head is red: the main branch's run list repeats reds that gate nothing, and the noise trains readers to ignore a red `ci-verdict` exactly where it does hold a merge.

## What Changes

- `scripts/ci_verdict.py` reads the judged run's `event` (from the fetched run record; a `--run-event` / `CI_VERDICT_RUN_EVENT` knob replays it without the API). When the event is neither empty nor `pull_request` — a `push`, `schedule`, or `workflow_dispatch` run at the default branch — and the judged verdict is GREEN while the head carries unjudged reds, the posted row is `neutral` and the exit is 0: not `success` (the head is not clean) and not `failure` (no merge is gated there). The existing `DEFAULT-BRANCH HEAD:` output line names the rule and keeps every unjudged red fully named.
- `pull_request` heads are unchanged: the #2116 forcing still reds a green judged run beside an unjudged red, because there the merger really refuses.
- A run whose OWN judged jobs are red keeps today's `failure` even when its event is `push` — the defect is only the unjudged-red forcing.
- `tests/test_ci_verdict.py` pins all four shapes, including a replay of the measured 2026-11-20T21:51Z main-head row set (green judged jobs + the two `implement` failure rows).
- No workflow change: `ci-verdict.yml` already passes the judged run's `RUN_ID`, and the run record's own `event` decides the arm.

## Impact

- `scripts/ci_verdict.py` — new `--run-event` argument; `default_branch_head` computed next to `run_event`; the `neutral` arm extended in the conclusion block; one output line.
- `tests/test_ci_verdict.py` — four new CLI-level fixtures.
- Not covered (separate issues, linked both ways): #2991 (the merge sweep defers on a stale `ci-verdict` artifact its own verdict replaces seconds later); #2992 (a CI run with a stalled `in_progress` job silences the verdict and merge sweep until it concludes).

Refs: issue #2993 (Problem/Why/fix/AC with the measured ids), side issues #2991, #2992.
