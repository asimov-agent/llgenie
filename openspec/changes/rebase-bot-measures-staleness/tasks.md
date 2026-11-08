## 1. The measurement (half A)

- [x] Add `staleness_from_compare()` to `scripts/check_pr_base.py` — the single definition of
      "behind" (merge-base != base tip), shared with the gate
- [x] Add `measure_behind()` to `scripts/rebase_bot_sweep.py` — reads `repos/<repo>/compare/<base>...<head>`
      and applies that definition; `None` when the payload is unreadable
- [x] Thread `behind` through `outcome()` so a measured-behind branch is `REBASE` whatever
      `mergeStateStatus` says
- [x] Measure EVERY candidate PR in `sweep()` (not only the ones whose state looked non-stale)

## 2. The coexistence narrow (half B)

- [x] Narrow `if red and state == "BEHIND"` to fire only when the PR is NOT measured behind
- [x] Record `behind` on the decision and name it in the per-PR reason lines

## 3. Proof

- [x] A test pins the measured shape: `BLOCKED` + `MERGEABLE` + behind ⇒ `REBASE`, not `NONE`
- [x] A test pins that checks-in-flight still skips a behind PR (cancel guard intact)
- [x] A test pins that a behind PR whose only red is the staleness gate is taken, not deferred
- [x] A test pins the negative (behind + measured fresh + red ⇒ still the fix-bot's)
- [x] A test pins that an unreadable compare is never read as "not behind" (#801)
- [x] Mutation-proved: reverting the fix reds 4 of the new tests, restoring greens all 99
- [x] Docs trio (#1123): this openspec change + `agent-wiki/` note + `docs/changes.d/` row
