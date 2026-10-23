## Why

`auto-merge.yml`'s `recheck` sweep runs on `cron: "*/30 * * * *"` (#546) and that cron has never produced a
run: 0 `schedule` runs out of 66 total, while `queued-alarm` (53), `fix-bot` (48), `issue-refiner` (45) and
`rebase-bot` (30) all fire on the same repository in the same window (measured 2026-10-23, issue #560).

`recheck` is the only retry for a deferral that clears **without a push** — an approving review, a
`do-not-merge` label removed, a secret added. The gate itself fires on CI completion, so with no push the cron
is the whole answer. Because it never ran, #559 and #556 sat green and unmerged until the gate was re-executed
by hand.

`*/30 * * * *` is the only cron in the tree that expands to EVEN minutes (`:00`, `:30`); every cron that fires
uses an odd minute, and the repository already documented the reason in `queued-alarm.yml` — *"an odd minute;
GitHub drops top-of-hour runs"* (#275, #301).

## What Changes

- `auto-merge.yml`: the sweep's cron moves from `*/30 * * * *` (`:00`, `:30`) to a pair of odd minutes at the
  same 30-minute cadence, with the measurement recorded in the comment beside it.
- `tests/test_bot_pipeline_isolation.py`: a new guard asserts every cron minute in every workflow is odd —
  derived from the workflow files, never a hand list — so `*/N`-at-zero cannot come back. A second guard
  keeps the sweep scheduled at all, so the always()-on-CI-completion path cannot quietly replace it.

Nothing else changes: the sweep's decision code, its make target (`make auto-merge-recheck`) and its
`if: always()` wiring on every CI completion stay exactly as #559 left them.

## Impact

- Affected spec: `bot-schedules` (new capability)
- Affected code: `.github/workflows/auto-merge.yml`, `tests/test_bot_pipeline_isolation.py`, `README.md`
- Verified end to end only after merge: a `schedule` trigger fires from the default branch, so the proof that
  the cron works is a non-zero `runs?event=schedule` count on the next 30-minute slot (see `Not covered` in
  issue #560 if it does not).
