# Proposal: zombie-run-retire

## Why

Issue #2600. Measured 2026-11-13 on main `2180f3cec`: `make check-zero-job-pending CANCEL=1`
re-reported the same five 2026-11-11 runs (43096752613, 43096752703, 43098130674, 43098130679,
43098130785) as stranded at 1645–1660 minutes while the cancel pass printed
`cancelled 0 stranded run(s), 5 already concluded` — a permanent red. The truth map measured this
session: the run LIST **and** the single-run REST API both report `status=queued, conclusion=null,
updated_at==created_at` (the REST row is stale/phantom), while GitHub's cancel endpoint answers
`Cannot cancel a workflow run that is completed` — the cancel answer is the only endpoint that
reflects the run's real state. `DELETE /actions/runs/{id}` (the cleanup GitHub designs for runs
pending >24h) returns 403 for the repo's `write`-level identities: no token the monitor carries
(`github.token`) can delete them. So the alarm can never clear: every scan re-faces the same
phantoms — the mechanism that produced the #2584–#2588 issue spam and breaches #2588's "never
reported a second time" criterion.

## What Changes

- **Retirement evidence is the cancel refusal.** A fix-mode run (`--cancel-stranded`) whose cancel
  is answered `already completed` CONFIRMS the candidate concluded; it is zombie-RETired, not a
  stranded finding: no per-run stranded issue, no forced-RED check-run, and instead a small
  deduped retirement record carrying a new marker `<!-- zero-job-zombie-retired: run N -->`
  (rendered through `issue_body.render`, the one body renderer).
- **Read-only scans retire from the record.** Before counting, the scan reads all issues
  (open OR closed) carrying the retirement marker and moves matching candidates to a named
  `zombie-retired` report line — never counted, never cancelled, never filed, never forced RED.
- **Exit rule:** the gate exits 0 when every candidate is retired (pre-scan from records, or
  newly confirmed AND recorded this pass); live starvation (cancel lands, runner arrived,
  delivery failure) keeps the existing red/exit-3 behavior exactly.
- `cancel_stranded`'s "already" docstring promise "the next scan will not name it" — the false
  promise at the heart of #2600 — is replaced with the retirement semantics that make it true.

## Impact

- Affected specs: `zero-job-pending` (ADDED requirement: cancel-refusal retirement with a
  persisted marker record).
- Affected code: `scripts/check_zero_job_pending.py`, `tests/test_check_zero_job_pending.py`,
  `zero-job-pending.yml` comments, docs fragment + agent-wiki note.
- Out of scope (separate linked issue): giving the monitor an admin-capable delete arm so
  confirmed phantoms are DELETED from the board, not just retired from counting.
- After merge, the scheduled monitor (`FILE=1 CANCEL=1`) confirms the five phantoms once, files
  five retirement records, and every later scan reports zero findings.
