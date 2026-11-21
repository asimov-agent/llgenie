# Trigger-green sweeps ignore the verdict lane's own stale artifact row (issue #2991)

## Why

The merge sweep deferred a fully green PR on a `ci-verdict` row its own verdict lane replaces seconds later (issue #2991). Measured on 2026-11-21 at PR #2990 head `8d4892e67…`: the `workflow_run` sweep (auto-merge run `44855608138`) read the head at `02:23:28Z` and logged `deferred to a human: head 8d4892e6 has a red check ci-verdict (failure, run 136684722878)` — a red artifact row posted by the PREVIOUS verdict attempt — while the fresh green verdict row for the same head landed at `02:23:38Z`, ten seconds after the read. The #2885 supersede collapse cannot clear that row at read time (the green row did not exist yet), and the sweep is triggered by the very verdict-lane completion whose row has not landed. The PR merged only hours later, after a head move re-fired the chain. A green, conflict-free PR whose only "red" is the verdict lane's own stale artifact is a wedge the lane manufactures against itself.

## What Changes

- `scripts/auto_merge.py`: `failing_checks` gains a `trigger_green` mode. When the sweep was triggered by a run that CONCLUDED GREEN at this head (the auto-merge `merge` job only runs under `workflow_run.conclusion == 'success'`), a concluded-red check-run row posted by the verdict lane's own workflow FILE (`ci-verdict.yml`, mirroring `ci_verdict.OUR_WORKFLOW_FILE` #2221) is not a deferral reason: it is named out loud as a stale verdict artifact and cleared. Every other red — including the per-attempt `ci-verdict` JOB row inside `ci.yml`, foreign unjudged reds, and any red at a sweep with NO green trigger (the scheduled `recheck`, `red-check`, `explain`) — still defers exactly as before.
- `run`, `_clear_review` and `_merge_review_cleared` thread `trigger_green` through their re-reads so a sweep never defers at a second read what its first read cleared.
- `scripts/auto_merge.py auto-merge` gains `--trigger-green`; `make auto-merge` gains `TRIGGER_GREEN=1`; `auto-merge.yml` passes `TRIGGER_GREEN=1` on the `merge` job step — legitimate because that job's `if` gate already asserts `github.event.workflow_run.conclusion == 'success'` at this head.
- The `auto-merge.yml` header documents the rule next to the #2885 collapse it extends.

## Impact

- Code: `scripts/auto_merge.py` (one new constant, `failing_checks` +3 named arms, `run`/`_clear_review`/`_merge_review_cleared` signatures), `mk/bots.mk` (`auto-merge` knob), `.github/workflows/auto-merge.yml` (knob pass-through + header note).
- Tests: `tests/test_auto_merge.py` grows four sweep-level tests mirroring the measured wedge (artifact cleared only with the trigger; `ci.yml` verdict JOB red still defers; foreign red still defers).
- No merge-power widening: the only red a green-triggered sweep stops honoring is the verdict lane's own posted artifact, whose truth the trigger's green conclusion already re-established for this head.
