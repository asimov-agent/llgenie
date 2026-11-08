# The rebase sweep now measures staleness instead of reading a label (issue #2071)

## The defect

`scripts/rebase_bot_sweep.py` decided whether a PR needed a rebase from `mergeStateStatus`:
`REBASE` only for `mergeable == CONFLICTING` or `mergeStateStatus in ("BEHIND", "DIRTY")`.
Nothing in the module measured a merge-base — a grep for `merge-base|ahead|behind|is-ancestor|rev-list`
found no call site.

That trusts the one field GitHub cannot give: `BLOCKED` is returned whenever a required review is
pending **or a check is failing**, and `UNSTABLE` for a failing check. A branch that falls behind
`main` and has any red check therefore never says `BEHIND`. It classified `NONE`, and the sweep's
only rebase was spent elsewhere.

Measured 2026-11-08 at `88ead5b9` — all six open PRs at once:

```
#2069 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
#2065 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
#2051 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
#2049 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
#1982 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
#1696 BLOCKED MERGEABLE merge-base(main)=d7f57cfa   (stale)
```

and rebase-bot run `42438486613` concluded `success` with `rebased: 0, failed: 0, bound: 10` —
a silent skip wearing a green run.

## The deadlock's two halves

1. Stale ⇒ `check-pr-base` reds ⇒ the PR is red ⇒ `mergeStateStatus` reads `BLOCKED` ⇒ skipped.
2. `if red and state == "BEHIND": … the fix-bot owns that` never fired, because a red PR does not
   report `BEHIND` — and the fix-bot repairs code, not lineage, so it could not clear
   `check-pr-base` even when it held a claim. Measured: it held five of the six, re-ran `success`,
   cleared none.

## What changed

**Half A — measure, don't infer.** `measure_behind()` reads
`repos/<repo>/compare/<base>...<head>` and applies `check_pr_base.staleness_from_compare()`: the
head is behind iff its merge-base is not the base tip — the exact rule `check-pr-base` enforces
(`Makefile:1136`, #845). The definition lives once, in the gate's own module, so the sweep cannot
drift from the gate it is trying to satisfy. `outcome()` takes it as a `behind` argument that
outranks the masked state, and `None` (an unreadable payload) is never "not behind" (#801 preserved).

**Half B — narrow the coexistence rule.** It now keys on the measured fact rather than the state
string: a measured-behind PR is this bot's even when red, because the rebase is the precondition for
the gate that is red. A PR red for a genuine failing test still belongs to the fix-bot.

**Reported per PR.** Every candidate is measured and the decision carries `behind`, so `rebased: 0`
can no longer be printed while a genuinely-behind PR was passed over.

## What did not change

The checks-in-flight skip (rebasing force-pushes and would cancel the deciding run), `UNKNOWN` →
`DEFER` (#453), a crashed read → `ERROR` (#801) with its PR-surface comment, the `bot-done` marker
bound (#457), the daily cap, and the stdout contract `rebase-bot.yml` reads
(`action=`/`pr=`/`head_branch=`/`head_repo=`) — the workflow needs no edit.

No gate was weakened; `check-pr-base`'s behaviour is untouched and the sweep now obeys it.

## Proof

- New tests pin: the exact measured shape (`BLOCKED`+`MERGEABLE`+behind ⇒ `REBASE`), the negative
  (measured fresh ⇒ passed over), the in-flight guard still winning over staleness, the half-B
  narrow in both directions, an unreadable read never read as "not behind", and that the shared
  definition is `check_pr_base`'s.
- Mutation-proved: with the `behind` branch and the narrow reverted, **4 of the new tests red**;
  restored, `tests/test_rebase_bot_sweep.py` + the three rebase siblings = **99 passed**.

## Files

- `scripts/rebase_bot_sweep.py` — `measure_behind()`, `outcome(behind=…)`, measurement in `sweep()`,
  narrowed fix-bot rule, `behind` on the decision.
- `scripts/check_pr_base.py` — `staleness_from_compare()`, the one staleness definition.
- `tests/test_rebase_bot_sweep.py` — the `compare` route in the fake `gh`, plus 8 new tests.
- `openspec/changes/rebase-bot-measures-staleness/` — this change (proposal, tasks, spec).
