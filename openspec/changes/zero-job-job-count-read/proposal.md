# Fix: read the zero-job count from the jobs array, not a key the projection lacks

## Why

`scripts/check_zero_job_pending.py` decided whether a dispatched run is stranded (`zero jobs`)
with `total = int((jobs.get("total_count") ...) or 0)` after `gh run view <rid> --json jobs`.
That projection returns `{"jobs": [...]}` with **no `total_count` key**, so the expression
evaluated `None or 0` → `0` for every run. Any queued/in-progress run older than `--minutes` was
classified as a stranded zero-job run and filed — including runs with live jobs
(run `42141213441`: `guard`/`matrix`/`engine-build-vllm-rocm`, real `total_count` 3).

## What changes

The job-count read counts the `jobs[]` array instead of the absent key:

```python
total = len((jobs.get("jobs") if isinstance(jobs, dict) else None) or [])
```

A run whose jobs array is non-empty has instantiated jobs and is never the zero-job case, however
long it has run. A genuinely jobless stranded dispatch is still filed as before; the
queued-behind-concurrency discriminator (#1704) is untouched. The three known filings
(#1823/#1822/#1709) name runs with live jobs and are re-checked against the true count.

## Who

ci-pipelines-maintainer (this lane owns the zero-job monitor).
