# 2026-11-02 `ci-verdict` refuses a truncated supersession listing

Issue **#1582** (gate defect; tagged `agent:implement`, AGENTS: this lane).

## What changed

`scripts/ci_verdict.py::superseding_run()` now refuses to reach a verdict when the managed
`actions/runs?branch={branch}&per_page=50` listing is truncated — the same invariant `jobs_of()`
already holds at its own listing. Before this change a branch with more than 50 runs (measured
`branch=main`: total_count 2500) silently truncated the supersession read: when the true later
run sat beyond the newest 50, `superseding_run` returned `None` and the verdict posted `failure`
for a superseded head — a false-red board quote (the #1111/#1250 stale-head class this gate exists
to close).

After: if `total_count > len(workflow_runs)` on the returned run listing, raise `RuntimeError`
(exit 2, "a truncated listing cannot be a verdict") — never a pass. For branches under 50 runs the
guard is silent and behaviour is unchanged: a later same-workflow same-branch run still yields
`neutral`; no later run still yields the decision the jobs rows imply.

## Verified

- Guard-proof both directions on `tests/test_ci_verdict.py`: pre-fix tree fails the new
  truncation test ("accepted a truncated listing as a verdict"); fixed tree passes all 22 (20
  existing + 2 new: truncated listing refuses even when the superseder hides; non-truncated
  listing still finds the superseder).
- Full `tests/test_ci_verdict.py` green in the CI container.
- No workflow-file change, no gate weakening: the guard add uses the module's own `jobs_of()`
  idiom.
