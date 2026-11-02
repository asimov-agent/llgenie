# check-pr-closing anchors the squash range at the live merge-base (issue #1527)

A correct PR reds on main's OWN commits because the gate's base was the pull_request event's frozen
`base.sha`. `ci.yml`'s guard step, `scope.yml`'s scope step and `pipeline.yml`'s unit job all fed
`github.event.pull_request.base.sha` as `PR_BASE`; that value is frozen at the last push, so once
main advances past the PR's fork point, the range `PR_BASE..HEAD` sweeps in every main commit that
landed after the frozen base — each carrying its own `Issue:`/`(#N)`/`closes` claims — and the gate
demands the PR body close them all.

Measured on #1453 (head `e9216ef3`): the range red with claims for #1467/#1470/#1471/#1506/#1507/#1511
and closes #1465/#1468/#1469/#1472/#1508 — NONE in the branch's own commit messages (token scan: only
`closes #1365` twice). Re-running the same script with `--base origin/main` (the live base) over the
same head + body was OK. A rerun did not fix it: the event payload itself is replayed.

## The fix

- The three workflows now pass the LIVE `origin/main` ref and fetch it first
  (`git fetch --no-tags --prune origin main`) so the merge-base is the current one, never a stale
  ref. A push to main has no `base_ref`; `origin/main` is then HEAD, so the range stays empty and only
  the static half runs.
- `scripts/check_pr_closing.py` resolves `--base` to `git merge-base <base> <rev>` before reading the
  range (the point at which the actual squash diverged), so a PR rebased onto newer main reads its OWN
  commits — the commits between the live merge-base and the head.

## Unit tests (proof it catches the bug)

- `test_a_pr_opened_before_a_main_advance_stays_green` builds a repo where a PR forks, main advances
  with its own claim (#9), and the PR head is rebased onto that new main: the live-base run is GREEN,
  and the SAME content read with the old frozen `base.sha` is RED — the regression the fix removes.
- `test_a_genuine_non_adjacent_claim_still_reds_with_the_live_base` proves the negative control: a PR
  whose own commit claim is only `closes **#N**` (markdown between keyword and ref, so not a close) is
  still RED under the live base. The live base stops the sweep; it does not disable the gate.
