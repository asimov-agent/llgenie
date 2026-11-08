# ci-verdict restores the gate contract: a cancelled/neutral unjudged row blocks again (issue #2237) — 2026-11-08

**Implements:** issue #2237 — `docs/BOTS.md` promised the verdict "can never call a head clean that the
merger will refuse", but after #2231 merged, `UNJUDGED_RED_CONCLUSIONS` became a STRICT SUBSET of
`auto_merge.RED_CONCLUSIONS`, so a PR head whose only unjudged row was a `cancelled`/`neutral` check-run
from a non-`ci-verdict` workflow read `ci-verdict: success` (green) while `auto_merge` refused the merge.

## Root cause

#2231 (fix for #2221) stopped a green `main` head redding on the verdict's OWN `judge` rows and on
`auto-merge`'s own `merge=cancelled` at a `main` push. It achieved the second by exempting the WHOLE
conclusion class — `UNJUDGED_RED_CONCLUSIONS = {failure, timed_out, startup_failure}` — instead of
exempting the specific workflow FILE whose rows are owed-nothing. That made the unjudged-red set a strict
subset of the merger's block set, silently reopening the #2116 false-green on PR heads.

Measured at `main` `da83db09` (branch base, before the change):

```
BLOCKING_CONCLUSIONS       = ['cancelled', 'failure', 'neutral', 'startup_failure', 'timed_out']
UNJUDGED_RED_CONCLUSIONS   = ['failure', 'startup_failure', 'timed_out']
UNJUDGED == BLOCKING? False     UNJUDGED subset? True   'cancelled' in auto_merge.RED? True
```

Behavior harness: `unjudged_reds()` on a `cancelled` row from `engine-build-pr-trigger.yml` (run 999)
returned `[]` → verdict would post `success` while `auto_merge` refuses that head.

## What changed

- **`scripts/ci_verdict.py`** — `UNJUDGED_RED_CONCLUSIONS` is pinned equal to `BLOCKING_CONCLUSIONS`
  (`= auto_merge.RED_CONCLUSIONS`), and `unjudged_reds` grants a transient exemption per WORKFLOW FILE
  (`TRANSIENT_FILES = {auto-merge.yml}`, `TRANSIENT_CONCLUSIONS = {cancelled, neutral}`), never per
  conclusion class. A `cancelled`/`neutral` row from any OTHER workflow is a named unjudged red; only
  auto-merge's OWN sweep and the verdict's own rows (`OUR_WORKFLOW_FILE`) are silent.
- **`tests/test_ci_verdict.py`** — `test_the_blocking_conclusions_are_the_merger_s_rule` now also
  asserts `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS` (the pin #2231 would not have
  shipped); `test_a_cancelled_unjudged_row_from_another_workflow_blocks` is the new negativity control;
  `test_auto_merges_own_cancelled_row_is_a_transient_not_a_blocker` (renamed) preserves the #2221
  auto-merge transient.
- **`docs/BOTS.md`** — the contract sentence now states the enforced behaviour: cancelled/neutral
  unjudged rows block and are named; only a workflow's OWN rows are exempted by file.

## Proven

Sabotage pair on the branch (`fix/2237-unjudged-red-subset` @ `da83db09`): reverting the `scripts`
fix while keeping the new tests produced `FAILED test_a_cancelled_unjudged_row_from_another_workflow_blocks`
and `FAILED test_the_blocking_conclusions_are_the_merger_s_rule`; restoring the fix produced `54 passed`.
Full `tests/test_ci_verdict.py` + `tests/test_ci_scope.py` + `tests/test_auto_merge.py`: 200 passed.
`make verdict-roster` and `make check-workflows` green.
