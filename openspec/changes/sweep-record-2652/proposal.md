# Proposal: sweep-record-2652 (issue #2652)

## Why

Issue #2652 is the sweepers' rolling record tracker: every auto-merge sweep run must
land one greppable line `[sweep <UTC-stamp>] merged=N approved=N deferred=N` there.
The record step was wired into the *Hermes cron prompts* (PR #2654), but host-side
Hermes cron was banned repo-wide on 2026-11-14 (AGENTS.md: profile cron machinery is
CI/test-only). Measured consequence: the last record comment on #2652 is
`[sweep 2026-11-14T15:42:07Z] …` (comment id 6880113566) — five days of live sweeps
(the `auto-merge.yml` scheduled lane, `make auto-merge-recheck`) produced **zero**
records. The tracker's AC "at least one real sweep run records here" cannot be met
continuously, and sweep evidence is once again invisible to the next reader on the
board.

## What Changes

- `scripts/auto_merge.py recheck` gains `--record <issue>`: when set (and not `--dry`),
  the sweep posts **one** record comment on the named issue after the sweep, first line
  exactly `[sweep <UTC-stamp>] merged=N approved=N deferred=N`, then one
  `#<num>: <reason>` line per PR this sweep deferred. Counts reflect the decisions
  this sweep actually took (merges it landed, approvals it posted, deferral markers it
  wrote).
- `make auto-merge-recheck` gains the `RECORD=<issue>` pass-through (`RECORD=2652`).
- The live sweeper — the `auto-merge.yml` lane's recheck step — passes
  `RECORD=2652`, so every scheduled sweep records on the tracker.
- The prompt copies stay as written (#2654): they name #2652 as the record target;
  the CI lane is what actually runs today.
- Tracker rule: this PR names #2652 in `Issue:` and does **not** close it — #2652 is
  a never-closing rolling tracker.

## Out of scope (tracked on #2652 itself)

- The `rebase-bot` lane's own record leg (its decision/actor loop spans several steps;
  its prompt already names #2652 and the record step there belongs to the lane's agent
  step, not the decide script).
