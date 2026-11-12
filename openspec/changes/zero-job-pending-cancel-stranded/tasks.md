# Tasks — zero-job-pending-cancel-stranded

- [x] 1. `scripts/check_zero_job_pending.py`: add `--cancel-stranded`; cancel every classified stranded
      run (including already-filed ones — the dedupe skip covers filing/RED only); re-read the run's
      jobs immediately before cancelling and skip the cancel (loudly report the skip) when a job has
      instantiated; print `cancelled N / skipped M` in the summary line.
- [x] 2. `tests/test_check_zero_job_pending.py`: cover the three spec scenarios hermetically — an
      already-filed stranded run gets cancelled but not re-filed; a run whose jobs re-read shows a live
      job is NOT cancelled; a queued-behind run is never reported, filed, or cancelled.
- [x] 3. `Makefile` target `check-zero-job-pending`: `CANCEL=1` passes `--cancel-stranded` by reference
      (mirrors the existing `FILE` knob); `.github/workflows/zero-job-pending.yml` monitor step invokes
      `FILE=1 CANCEL=1`.
- [x] 4. Filed-issue body: the `How we fix it` steps name the automatic remedy (monitor cancels the
      stranded zero-job run) beside the manual runner steps.
- [x] 5. Docs in the same commit as the change: `agent-wiki/2026-11-12-zero-job-pending-cancel-stranded-2571.md`
      (names the issue and PR) and `docs/changes.d/2026-11-12-zero-job-pending-cancel-stranded-2571.md`.
- [x] 6. Verification (tick only with rc=0 evidence): `python3 -m pytest tests/test_check_zero_job_pending.py -q`
      (13/13 rc=0), `make check-wiring` (rc=0), and `make openspec-validate NAME=zero-job-pending-cancel-stranded`
      (rc=0) all exit 0. The fast-gate bundle `make lane-preflight` passes at this head (result recorded in the PR).
