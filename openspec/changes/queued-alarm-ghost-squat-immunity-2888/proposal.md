# queued-alarm-ghost-squat-immunity-2888

## Why

The scheduled `queued-alarm` lane concludes `failure` on EVERY run since 2026-11-15 (measured:
`43761135658`, `43783445282`, `43827145631`, `43928631269`, `44000226765`, `44066878815`), each time
for the same six ghost run rows created 2026-11-11 on two deleted branches: `43096752585`,
`43096752613`, `43096752703`, `43098130674`, `43098130679`, `43098130785`. GitHub's own cancel
endpoint confirms all six CONCLUDED (re-measured 2026-11-17, 6/6 refusals: "Cannot cancel a workflow
run that is completed"). Five are retired in the zero-job ledger (#2600 mechanism, issues #2601–#2605);
the sixth (`43096752585`) has ONE completed job while its row stays stuck `queued` — it has jobs, so
the zero-job gate can never retire it. `queued_run_alarm.squat_runs()` consults neither the ledger nor
the job conclusions, so it counts all six as live squat forever. The episode issue #2683 that named
them is closed — closing an episode does not change what the detector counts. A permanently red
liveness monitor can never flag a REAL squat (issue #2888).

## What Changes

queued-run-alarm capability:

- The run-level squat scan SHALL consult the zero-job retirement ledger
  (`check_zero_job_pending.zombie_retired_run_ids`, #2600) once per scan. Ledger ids are reported as
  `retired` — named, never counted toward the squat episode, never trigger a filing, and the squat
  scan spends no jobs/branch/PR round-trip on them.
- A non-ledger candidate that is orphaned (branch 404, no OPEN PR) AND past GitHub's own 24h queued
  window AND whose instantiated jobs are ALL concluded SHALL be classified a CONFIRMED-CONCLUDED GHOST:
  named in its own report bucket, never counted as squat, never cancelled, never filed (this is
  `43096752585`: 1 job, completed, row stuck).
- Live squat semantics are UNCHANGED: an orphan-queued or expired run that instantiated no jobs, or
  whose jobs are not all concluded, stays RED and gets an issue filed exactly as today. The alarm
  never cancels and never files retirements — those stay the zero-job lane's (#2600) and the owner's.
- `scripts/package-layers.json` declares the new `queued_run_alarm -> check_zero_job_pending` import
  edge (Bots and automation → Structural gates).
- The scan gains a `--dry` switch (make `DRY=1`): full reads, full printed report, NOTHING filed,
  same exit codes — the principal for host-side replays and gate proofs; the scheduled lane keeps
  filing as today.

## Impact

- `scripts/queued_run_alarm.py` (`squat_runs`, `render_squat`, `main` exit classification),
  `scripts/package-layers.json`, `tests/test_queued_run_alarm.py`.
- No behavior change for live squat, stuck-job rows, or delivery channels. No new cancellations.
- The six phantom rows themselves stay parked for admin DELETE — already tracked by #2606.
