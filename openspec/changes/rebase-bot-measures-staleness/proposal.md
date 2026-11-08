## Why

The rebase sweep could not see a PR that is stale **and** red. `scripts/rebase_bot_sweep.py::outcome()`
classified `REBASE` only from `mergeable == CONFLICTING` or `mergeStateStatus in ("BEHIND", "DIRTY")`.
GitHub reports `mergeStateStatus=BLOCKED` whenever a required review is pending **or a check is
failing**, and `UNSTABLE` for a failing check — so a branch that is genuinely behind `main` never
carries the one state the sweep trusted. It classified `NONE` and was passed over silently.

Measured 2026-11-08 at `origin/main@88ead5b9` — **all six open PRs** were simultaneously
`mergeStateStatus=BLOCKED`, `mergeable=MERGEABLE`, and `merge-base(main)=d7f57cfa` (genuinely
behind). A live rebase-bot dispatch (run `42438486613`) reported `rebased: 0, failed: 0` and did
nothing: a silent skip wearing a green run.

The deadlock had two halves, and both had to be closed:

1. Being stale fails `check-pr-base` (`HEAD is NOT cut from origin/main`) → `linux/unit` reds →
   the PR is red → `mergeStateStatus` reads `BLOCKED` → the sweep skips it.
2. The sweep's coexistence rule (`if red and state == "BEHIND": … the fix-bot owns that`) only
   fired when the state string was literally `BEHIND`, which a red PR never reports — and the
   fix-bot repairs **code, not branch lineage**, so it could never clear `check-pr-base` anyway.
   Measured: fix-bot held claims on five of the six, re-ran `success` repeatedly, and cleared none.

## What changes

- **Half A — measure staleness directly.** `measure_behind()` reads the head's lineage through the
  platform's own `compare` endpoint, and `outcome()` takes it as a new `behind` argument that
  outranks the masked state. The definition lives ONCE, in
  `scripts/check_pr_base.py::staleness_from_compare()` — the merge-base-is-not-the-base-tip rule
  `check-pr-base` already enforces (`Makefile:1136`, issue #845) — so the sweep and the gate cannot
  drift apart. `None` (an unreadable payload) is never "not behind".
- **Half B — narrow the fix-bot rule.** The rule now keys on the measured fact, not the state
  string: a measured-behind PR is this bot's even when it is red, because the rebase is the
  precondition for the gate that is red. A PR that is red for a real failing test stays the
  fix-bot's.
- **The report names it.** Every PR is measured, and the decision carries `behind` plus a reason
  line, so `rebased: 0` cannot be printed while a genuinely-behind PR was passed over.

## What stays exactly as it was

- the **checks-in-flight skip** — a rebase force-pushes, which cancels the run deciding the PR;
- `UNKNOWN` → `DEFER` (#453) — still a deferral, still re-queried;
- a crashed read → `ERROR` (#801) — still an error, still surfaced on the PR;
- the `bot-done` marker bound (#457) and the daily cap;
- the stdout contract `.github/workflows/rebase-bot.yml` reads (`action=`, `pr=`, `head_branch=`,
  `head_repo=`) — unchanged, so the workflow needs no edit.

No gate is weakened: `check-pr-base` is untouched in behaviour, and this change makes the sweep
obey the same rule the gate enforces.
