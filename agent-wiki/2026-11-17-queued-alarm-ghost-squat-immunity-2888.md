# 2026-11-17 — queued-alarm ghost-squat immunity (#2888)

## What was verified

The scheduled queued-alarm lane had reddened on every run since 2026-11-15 (measured: 43761135658,
43783445282, 43827145631, 43928631269, 44000226765, 44066878815) on the SAME six 2026-11-11 ghost
rows: 43096752585, 43096752613, 43096752703, 43098130674, 43098130679, 43098130785. `gh run cancel`
refuses all six — "Cannot cancel a workflow run that is completed" — yet the squat scan kept counting
them as live squat forever. Five live in the zero-job retirement ledger (#2600, retirement issues
#2601–#2605); the sixth (43096752585: one completed job, row stuck `in_progress`, branch 404, PR
merged) can never enter the zero-job ledger because it HAS jobs.

Fix (`scripts/queued_run_alarm.py`):

- `squat_runs()` now consults `check_zero_job_pending.zombie_retired_run_ids(repo)` ONCE per scan and
  classifies ledger ids as RETIRED before paying its own jobs/branch/PR round-trips.
- A non-ledger candidate past GitHub's own 24h queued window whose instantiated jobs have ALL
  concluded, tracked by no OPEN PR, with its head branch gone (404 or null) is a CONFIRMED-CONCLUDED
  GHOST: named in its own bucket, never counted, never filed, never cancelled (row admin-only, #2606).
- LIVE squat semantics are UNCHANGED: orphan-queued runs whose jobs never instantiated and job-expiry
  residue still inside 24h (#1889) still redden the lane and file one deduped episode; cancellation
  stays the owner's word.
- `--dry` already existed (report without filing); it is now the host-side proof replay
  (`make queued-alarm DRY=1`) and stays filing-free.

Proofs (all measured 2026-11-17 in the worktree off origin/main):

- `tests/test_queued_run_alarm.py tests/test_check_zero_job_pending.py` → 47 passed, rc=0 (43
  pre-existing tests green UNCHANGED + 4 new #2888 tests: ledger-retired named with no extra
  round-trip, concluded-ghost named clean, live orphan still RED+filed, mix names all three and the
  filed episode keys on the LIVE id alone).
- Real-scan replay `make -s queued-alarm DRY=1` → exit 0, "clean: 1 confirmed-concluded ghost(s),
  5 ledger-retired row(s) named, no live squat" — the six ids named, nothing filed. Before the fix
  the same scan exited 1 with "6 squat".
- `make -s check-package-layers` rc=0 after registering the `queued_run_alarm → check_zero_job_pending`
  edge (Bots and automation → Structural gates); the scan reads the ledger through the ONE module that
  owns it.

## Decisions

- Ghost classification requires PAST-24h + instantiated jobs + all-concluded + no OPEN PR + branch gone;
  residue inside 24h stays job-expiry RED exactly as #1889/#2656 designed, so no live-squat semantics
  moved.
- The ledger is the authority for its ids: the squat scan asks GitHub nothing more about them.
- `squat_runs()` returns a 4-tuple (orphans, expired, ghosts, retired); only the first two count.

## Current status

Issue #2888, branch `feat/queued-alarm-ghost-squat-immunity-2888`, PR against main. OpenSpec change
`queued-alarm-ghost-squat-immunity-2888` validates. The scheduled lane's next run is the landing watch:
it must scan green with the six ids named.
