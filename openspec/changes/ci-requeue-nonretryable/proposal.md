# ci-requeue-nonretryable

## Why

`main` at `faa1af30` carries a red `requeue` check because the requeue sweep treats a run GitHub refuses to
retry as a fatal error. Measured 2026-11-08, run 42521844159 job 128856856724:

```
[requeue] gh run rerun 42521713581 --repo asimov-agent/llgenie --failed failed (1): run 42521713581 cannot be rerun; This workflow run cannot be retried
make: *** [Makefile:969: ci-requeue-cancelled] Error 1
```

`This workflow run cannot be retried` is GitHub answering with a **decision**, not a transient failure: a
run whose workflow was deleted, whose artefacts expired, or whose conclusion cannot be retried answers this
forever, so retrying the sweep can never clear it. One such run reds the whole job, and that red blocks every
merge (ci-verdict reports it as UNJUDGED RED) at a green `ci.yml`, a red no PR author can fix.

## What changes

1. `plan()` classifies a cancelled run whose `/jobs` listing has `total_count == 0` (nothing was
   instantiated) as non-retryable and lands it in the SKIP bucket WITHOUT dispatching a rerun — the cheap,
   deterministic DRY classifier for the measured shape.
2. `rerun()` captures the `gh run rerun` non-zero stderr and, when it carries a
   `NON_RETRYABLE_MARKERS` phrase (`cannot be retried` / `cannot be rerun`), records that run as SKIPPED
   with the refusal as its `why`, returns `"skip"`, and the sweep keeps going and exits 0 — the runtime
   classifier for the shapes the DRY probe cannot see.
3. A genuinely transient `gh run rerun` failure (rate limit, 5xx, auth) STILL raises and aborts non-zero — a
   real problem is never swallowed by the refusal skip (negative control, named test).
4. `tests/test_ci_requeue.py` gains four tests: the zero-job plan skip, the DRY skip bucket, the runtime
   refusal skip-while-continuing, and the transient-is-still-fatal negative control.

## Change-first

Issue #2295 is the surviving tracker. The healer's `workflow_run`-origin skip (#1451) is preserved; this
adds the zero-job and runtime-refusal classes beside it. `ci-verdict`'s judging of `requeue` is untouched;
the gate just stops reddening on GitHub's decided refusal. Branch: `fix/2295-requeue-nonretryable`.
