# 2026-11-14 — the queued-alarm classifies and names the ghost-run squat (issue #2656, PR #PRNUM)

## What was verified

- Issue #2656's measured shape held: six runs squatted non-terminal for 3 days — five `queued`
  since 2026-11-11 20:33-20:47Z with empty `pull_requests` and deleted head branches (both
  `feat/2472-semgrep-ghost-runs` and `feat/engine-bump-regen-guard` 404 on the git refs API), and a
  sixth (43096752585) `in_progress` whose job records expired to the single ci-verdict self row
  (conclusion `failure`) — the job-expiry trap of #1837/#1889. The job-row scan reads all six CLEAN,
  so the alarm that fires twice an hour never named them.
- `scripts/queued_run_alarm.py` now classifies the runs still non-terminal past `--minutes`:
  ORPHAN (no open PR + head branch deleted/404; a transient read is treated as present so a live run
  is never mis-called), EXPIRED (`in_progress` whose jobs all concluded — read as job expiry #1889,
  never a live matrix), else LIVE.
- The squat is rendered and (with `--comment`) filed as ONE deduped episode issue keyed on the sorted
  run-id set (`queued-run-squat episode <ids>` marker), rendered through the one issue-body renderer.
- Never a cancel: the alarm never issues `gh run cancel`/delete; the handling rule is written in
  `docs/BOTS.md`, gated on the owner's explicit word.
- `tests/test_queued_run_alarm.py`: orphan/live/open-PR/expired/live-in_progress classification,
  once-per-episode dedupe, never-cancel, episode marker sorted — 26 passed (host python, rc=0).

## Key decisions

- The orphan evidence is an affirmative git-ref 404, not a guessed timestamp or a stale list row; a
  transient read failure is conservatively treated as present.
- The episode is keyed on the run-id SET, so the same squat is reported once and a newly added run
  starts a fresh episode instead of being swallowed by an old marker.
- The zero-job monitor (#1410/#1704/#2600) keeps its own job — this change is the run-level
  complement that reads the trapped in_progress as expiry, which nothing else did.

## Current status

OpenSpec change `ci-queued-squat-classify` written (task 6 notes that the OpenSpec CLI could not be
executed in the agent container — no docker daemon and no node/npm — so `openspec validate` runs in
CI's node-bearing environment; tasks 1-5 were hand-crafted to the CLI's canonical shape). The code and
tests are implemented and green locally; the PR is driven to green and opened by the issue-bot.
