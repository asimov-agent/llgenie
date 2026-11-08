# ci-requeue treats GitHub's "cannot be retried" as a decision, not a fatal error (issue #2295) — 2026-11-08

**Implements:** issue #2295 — the requeue sweep reddened `main` at `faa1af30` because it treated a run GitHub
refuses to retry as a fatal error, at a green `ci.yml` (10/10), a red no PR author can clear.

## Root cause

Measured 2026-11-08, run 42521844159 job 128856856724 at `faa1af30`:

```
[requeue] gh run rerun 42521713581 --repo asimov-agent/llgenie --failed failed (1): run 42521713581 cannot be rerun; This workflow run cannot be retried
make: *** [Makefile:969: ci-requeue-cancelled] Error 1
```

`This workflow run cannot be retried` is GitHub answering with a **decision**, not a transient failure: a run
whose workflow was deleted, whose artefacts expired, or whose conclusion cannot be retried answers this
forever, so a sweep retry can never clear it. One such run reddened the whole job, which `ci-verdict` carried
as UNJUDGED RED and every open PR inherited.

## Fix

- `plan()` classifies a cancelled run whose `/jobs` `total_count == 0` (nothing instantiated) as
  non-retryable and lands it in the SKIP bucket WITHOUT a dispatch — the cheap deterministic DRY classifier.
- `rerun()` captures the non-zero `gh run rerun` stderr; a `NON_RETRYABLE_MARKERS` phrase (`cannot be
  retried` / `cannot be rerun`) records the run as skipped and the sweep continues and exits 0 (runtime
  classifier for shapes the DRY probe cannot see).
- Any OTHER non-zero return (rate limit, 5xx, auth) still raises — a real problem is never swallowed
  (negative control, named test).

## Verification

- `tests/test_ci_requeue.py` 18 passed (incl 4 new: zero-job plan skip, DRY skip bucket, runtime refusal
  skip-while-continuing, transient-is-still-fatal negative control).
- Files: `scripts/ci_requeue.py`, `tests/test_ci_requeue.py`, `Makefile` (`##` help), `docs/BOTS.md`,
  openspec change `ci-requeue-nonretryable/`, note pair + `CHANGES.md` row.
