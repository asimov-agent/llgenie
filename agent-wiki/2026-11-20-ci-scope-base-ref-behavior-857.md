# ci-scope base-ref fallback: pin the behaviour, not the spelling (issue #857)

Issue: #857. PR: pending (feat/ci-scope-behavior-fallback-857).

## What was wrong

The `scope` job's classify step once carried `assert "${EVENT_BASE_REF:-main}" in body` — a pin on
the implementation's *syntax*. Any correct rewrite (moving resolution into `scripts/`, using
`github.base_ref || 'main'`) would have redden a test whose subject never changed, while the
behaviour itself — an event without a base_ref must still classify against `origin/main`, loudly —
was never executed by any test. The step has since been re-spelled (`if [ -z "$BASE" ]` + an
echo + `BASE=main`), which deleted the grep pin without replacing it: at the baseline a planted edit
removing the whole fallback block would have kept the whole battery green while the classifier
diffed against the empty string.

## What was verified against the spec

- New pins in `tests/test_ci_scope.py` EXECUTE the step's `run:` body under bash with `make`/`git`
  stubbed to record their argv, after substituting `${{ github.base_ref }}` /
  `${{ github.event_name }}` for the event shape:
  - empty base_ref ⇒ `make ci-scope BASE=origin/main` (resolution);
  - the stdout names the event and the fallback (`No github.base_ref for event 'workflow_dispatch'`)
    (visibility);
  - a real base_ref ⇒ `BASE=origin/feat/x`, no fallback line.
- Negative controls (planted body variants): fallback block deleted ⇒ recorded ref is `BASE=origin/`
  and the resolution pin fails; echo line deleted ⇒ resolution holds but visibility fails.
- `pytest tests/test_ci_scope.py tests/test_ci_scope_trigger.py` → 57 passed (10 new lines of
  harness + 5 pins; `scope.yml` untouched).

## Decisions

- The stubbed-execution harness reads the step body straight out of `scope.yml`, so the pin cannot
  drift from the workflow: the test follows the step wherever its spelling goes, which is the point
  of #857.
- AC4 ("the grep assert gone") needed no work: the rewrite the issue predicted had already landed;
  the residual defect was the missing behavioural pin, which this lane adds.

## Current status

Implementation + focused suites green on the lane tree; full unit battery and preflight drive the PR.
