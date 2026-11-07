# fix-rebase-bot-fork-head-robustness

## Why

The rebase-bot failed 3/3 dispatched runs today (06:15, 06:50, 08:05). In the 08:05 run
(42354009408, head 6b7141ef) both eligible fork-head PRs reddened the whole sweep, each on a
guard the actor was meant to provide:

- **#1901** (transient read): the actor resolved the CHANGES.md conflict, passed the structural
  gates and the squash-close re-check, then the single push-time live `gh pr view` (dead-vehicle
  re-read, issue #1733) returned rc=1 once and the whole run aborted as a false red. A transient
  gh relay fault is not evidence a PR merged — the #1602/#1603 discipline (a transient read-fault
  is retried; a persistent one still fails closed) had not reached this guard.
- **#1926** (fork fetch): `git fetch fork ci/1924-skill-code-parity --quiet` failed with
  "insufficient permission for adding an object to repository database .git/objects". The fetch
  runs without `set -e` behind it, so the fault slipped past; `git checkout -B` then failed on a
  ref that never arrived, and the actor cascaded onto a rebase of WHATEVER branch was last checked
  out (main) — a wrong-vehicle push that the squash-close re-check caught only by accident.

Issue: [#1952](https://github.com/asimov-agent/llgenie/issues/1952).

## What Changes

- `scripts/rebase_bot.sh` fetches the PR head through a bounded retry (3 attempts) that ALSO
  verifies `refs/remotes/<remote>/<branch>` exists before the checkout; a fetch that cannot make
  the ref land is a named, per-PR `gave-up` stop (comment + exit) that lets the sweep continue and
  never rebases a different branch.
- After the checkout, the actor verifies HEAD actually landed on `$HEAD_BRANCH` and refuses to
  rebase when it did not (the same silent-slip class as the fetch).
- The push-time dead-vehicle `gh pr view` re-read is bounded-retried (3 attempts) so a single
  transient rc=1 does not redden the sweep; a persistent unreadable state still fails closed
  (issue #1733) exactly as before.
- New tests: a transient push-time read fault is retried and the branch is pushed; a persistent
  read fault still refuses; a fork fetch object-write fault is a named skip, not a wrong-branch
  rebase. Each asserts the branch is untouched on the fail path and genuinely published on the
  retry path.

## Impact

- Affected specs: `rebase-bot-sweep` (modified — fork-head fetch and push-time re-read are robust
  to transient object-write/read faults; a fetch that cannot land is a named skip).
- Affected code: `scripts/rebase_bot.sh`, `tests/test_rebase_bot_sweep.py`, `agent-wiki/`.

## Not covered

- The two claimed PRs themselves (#1901, #1926) stay under their live run-failure-reactor claims;
  this change only makes the workflow robust so the NEXT run can rebase them.
