# 2026-11-07 — rebase-bot robust to transient fork-head fetch and push-time read faults (issue #1952)

## What was wrong

3/3 dispatched rebase-bot runs failed today (06:15, 06:50, 08:05). In the 08:05 run
(42354009408, head 6b7141ef) both eligible fork-head PRs reddened the whole sweep:

- **#1901** — a single transient `gh pr view` rc=1 at push time (the dead-vehicle re-read, issue
  #1733) aborted the run after the conflict was fully resolved. A transient read fault is not
  evidence of a merge — the #1602/#1603 retry-hardening discipline had not reached this guard.
- **#1926** — `git fetch fork ci/1924-skill-code-parity` faulted on the runner's `.git/objects`
  ("insufficient permission for adding an object to repository database"). The fetch runs without
  `set -e`, so the failure slipped past; the checkout then failed on a ref that never arrived and
  the actor cascaded onto whatever branch was last checked out (main) — a wrong-vehicle rebase/push
  the squash-close re-check caught only by accident.

## What changed

- `scripts/rebase_bot.sh`: the PR-head fetch is a bounded retry (3 attempts) that ALSO verifies
  `refs/remotes/<remote>/<branch>` exists; a fetch that cannot make the ref land is a named,
  per-PR `gave-up` stop (comment + exit) that lets the sweep continue — never a rebase of a
  different branch.
- After the checkout, HEAD is verified to have landed on `$HEAD_BRANCH`; a silent-slip checkout
  refuses to rebase.
- The push-time dead-vehicle `gh pr view` is bounded-retried (3 attempts); a single transient
  fault no longer reddens the sweep, while a persistent unreadable state still fails closed
  (issue #1733).
- New tests: transient-read retry really pushes; persistent-read still refuses; fork-fetch fault
  is a named skip, not a wrong-branch rebase. OpenSpec change `fix-rebase-bot-fork-head-robustness`.

## Verified

- Guard-prove RED/GREEN: with the fix stashed, the transient-read test and the fork-fetch test
  both fail (old code reddens / cascades); with the fix restored, all pass.
- `pytest tests/test_rebase_bot_sweep.py` 57 passed.
- `make openspec-validate NAME=fix-rebase-bot-fork-head-robustness` exits 0.

## Status

Issue #1952; PR from `fix/1952-rebase-bot-fork-push` against `asimov-agent/llgenie:main`. Waiting
for review — the agent never merges.
