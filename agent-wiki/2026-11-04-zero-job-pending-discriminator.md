# Zero-job-pending discriminator: queueing is not "no runner matched" (#1704)

The zero-job-pending monitor (#1410) distinguishes a queueing run from a stranded one before it
files, and forces a genuinely stranded run's head RED.

## The defect

`scripts/check_zero_job_pending.py` keyed solely on `jobs.total_count == 0` (one signal, no reason
discriminator), so every zero-job run past the threshold was reported as "**No runner matched the
requested labels**". But `engine-build` serialises builds per `engine × arch` concurrency group
(#917, `cancel-in-progress: false`), so a `workflow_dispatch` run queued behind a sibling holding
the same group reads `queued`, zero jobs, older than the threshold — it is **queueing**, not
stranded. Six consecutive filings were false positives (#1473/#1536/#1569/#1699/#1700/#1701), each
closed as a one-off, while a run that TRULY can never get a runner parked as eternal `pending`,
readable as a working matrix.

## The discriminator

A zero-job run is classified by its concurrency state, not just by `total_count == 0`:

- **`queued_behind`** — the run reads `queued` and a sibling of the **same workflow** is
  `in_progress` holding the concurrency group. It is queueing; its jobs instantiate when the sibling
  finishes. It is reported as such and **never filed** as "no runner matched".
- **`stranded`** — the group is free (no same-workflow in_progress sibling) and the zero jobs
  persist. This is the genuine #1410 case (runner starvation): **filed once, deduped**, and its head
  is forced RED via the `ci-verdict` check-run path.

## Forced RED

A `pending`/`queued` zero-job run publishes no scope decision — and `scripts/ci_scope.py::verify`
already reds "no decision". But the run never CONCLUDES, so `ci-verdict`'s own
`workflow_run: [completed]` hook never fires on it. The monitor posts the same `ci-verdict` FAILURE
check-run payload `scripts/ci_verdict.py` would post, so a truly-unrunnable dispatch surfaces as a
failed check with a reason instead of an eternal `pending`. This requires `checks: write` in
`.github/workflows/zero-job-pending.yml`.

## Acceptance evidence

- Guard tests plant BOTH arms and assert the call counts: one stranded run -> **exactly one** issue
  create **and exactly one** `ci-verdict` check-run POST; a queued-behind run with `--file` ->
  **zero** issues and **zero** check-run POSTs (`tests/test_check_zero_job_pending.py`).
- The six superseded scan-issues stay closed as superseded; no further of their shape is filed for a
  queueing (non-stranded) run.
- `make check-docs check-workflows check-wiring lint` green on the PR.
