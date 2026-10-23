# 2026-10-23 — the auto-merge sweep's cron was never going to fire (#560)

**Issue:** [#560](https://github.com/asimov-agent/llgenie/issues/560) · **PR:** [#562](https://github.com/asimov-agent/llgenie/pull/562)

## What was wrong

`auto-merge.yml` carried its `recheck` sweep on `cron: "*/30 * * * *"` (#546). Measured on `main`
(`352e190`, 2026-10-23 10:25Z) that cron had produced **0** `schedule` runs out of 66 total, with the
workflow reporting `state: active` and the file on the default branch — about 6 slots missed. Every other
scheduled workflow in the same repository fired in the same window: `queued-alarm` 53, `fix-bot` 48,
`issue-refiner` 45, `rebase-bot` 30.

`*/30 * * * *` was the only cron in the tree expanding to **even** minutes (`:00`, `:30`); every cron that
fires uses an odd minute, and `queued-alarm.yml` had already recorded why (`an odd minute; GitHub drops
top-of-hour runs`, #275/#301).

`recheck` is the only retry for a deferral that clears **without a push** — an approving review, a
`do-not-merge` removed, a secret added. So a dead cron meant a deferral was never revisited: #559 and #556
sat green and unmerged until the gate run was re-executed by hand (`gh run rerun 39937509050`, attempt 2 —
which then approved as `asimov-agent` and merged both).

## What changed

- `.github/workflows/auto-merge.yml`: `cron: "*/30 * * * *"` → `cron: "3,33 * * * *"`, same 30-minute
  cadence, with the measurement and the odd-minute rule written beside it. The sweep's code, its
  `make auto-merge-recheck` target and its `if: always()` wiring on every CI completion are untouched.
- `tests/test_bot_pipeline_isolation.py`: two guards, both derived from the workflow files (never a hand
  list — the #301 rule):
  - `test_every_cron_minute_is_odd` fails on any cron whose minute field expands to an even minute, naming the
    workflow and the minute;
  - `test_the_auto_merge_sweep_stays_scheduled` keeps the sweep's schedule in place (one cron, 30-minute
    cadence, odd minutes, `recheck` job calling the one make target), because the CI-completion retry added by
    #558 cannot retry a deferral that clears with no push at all.
- `README.md`: the bot-slot table gains the sweep's slot, and the isolation section states the odd-minute rule
  with the measured numbers; the deferral paragraph names the new cron.

## Verified

- `pytest tests/test_bot_pipeline_isolation.py` in `llgenie/test:latest`: **6 passed** on the new cron.
- The same file with `*/30 * * * *` restored: **2 failed** —
  `auto-merge.yml: '*/30 * * * *' lands on an even minute — that slot produced 0 runs (issue #560)` and the
  derived guard naming minutes `[0, 30]`. So both guards fail on the old cron and pass on the new one.
- `make test-unit` and `make openspec-validate` green (see the PR's CI run).

## Not verified here

A `schedule` trigger fires only from the default branch, so the proof that the new cron runs cannot exist
before the merge. The check after landing is
`gh api repos/asimov-agent/llgenie/actions/workflows/auto-merge.yml/runs?event=schedule --jq .total_count`
non-zero within the first hour, and it stays open in #560's `Not covered` if it is still zero.
