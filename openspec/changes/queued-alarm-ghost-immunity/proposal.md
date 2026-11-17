# Proposal: queued-alarm-ghost-immunity

## Why

Issue #2600. Measured 2026-11-17 on main `184ea99defcb4b492bc079c762561197feb26859`: the scheduled
`queued-alarm` lane has concluded `failure` on EVERY run since 2026-11-15 (runs 43761135658,
43783445282, 43827145631, 43928631269, 44000226765, 44066878815), each red for the same six ghost
run rows that have squatted the queue since 2026-11-11: `43096752585`, `43096752613`, `43096752703`,
`43098130674`, `43098130679`, `43098130785` — all on deleted branches (`feat/2472-semgrep-ghost-runs`
and `feat/engine-bump-regen-guard`), no open PR, rows still reported `queued`/`in_progress` in the
runs list. GitHub's cancel endpoint confirms all six are CONCLUDED (`Cannot cancel a workflow run
that is completed`, 6/6 re-measured 2026-11-17). Five are ALREADY retired in the zero-job zombie
ledger (issues #2601–#2605; the mechanism of #2600); the sixth, `43096752585`, has ONE job whose
status is `completed` while its run row stays stuck — it has jobs, so the zero-job gate can never
retire it. Today `queued_run_alarm.squat_runs()` consults neither the retirement ledger nor a
concluded-jobs read, so it counts all six rows as live ghost squat on every scan, reddening the lane
forever — a liveness monitor that is permanently red is worth zero.

## What Changes

- **The squat detector learns the retirement ledger it shares with the zero-job gate.** `squat_runs()`
  reads `check_zero_job_pending.zombie_retired_run_ids(repo)` — the ONE confirmed-concluded-phantom
  ledger — and reports ledger ids as `retired (confirmed concluded earlier, #2600 mechanism;
  admin-only row, see #2606)`: NAMED but never counted, never cancelled, never filed, and no `run
  view` round-trip spent on them.
- **A read-only concluded-jobs probe for non-ledger candidates.** A run row past its 24h
  queue-expiry window (`QUEUE_EXPIRY_MINUTES`) that is ORPHANED (no open PR, head branch deleted) AND
  whose instantiated jobs have ALL concluded cannot progress any further — a confirmed-concluded
  ghost. It is named in its own bucket, never counted, never cancelled. This is what catches
  `43096752585` (jobs: 1, completed; row stuck) that the zero-job gate cannot retire.
- **Live squat semantics are UNCHANGED.** A queued run with a still-pending job, or an expired
  `in_progress` run whose jobs are still active, stays a RED finding and is filed exactly as today.
  "Never cancel a run" remains the alarm's standing rule — the fix reads ledgers and job rows, it
  never cancels, never deletes, never files retirement.

## Impact

- Affected specs: `queued-run-alarm` (ADDED requirements: retirement-ledger read; read-only
  confirmed-concluded probe; never-cancel/never-file preserved for the ghost classes).
- Affected code: `scripts/queued_run_alarm.py`, `scripts/package-layers.json` (the
  `queued_run_alarm -> check_zero_job_pending` edge), `tests/test_queued_run_alarm.py`, this change,
  a docs fragment, and an agent-wiki note.
