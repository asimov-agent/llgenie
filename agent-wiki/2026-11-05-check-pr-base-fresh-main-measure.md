# check-pr-base measures against freshly-fetched main (issue #1734)

`scripts/check_pr_base.py` (the #845 foreign-commit gate) measured a branch against whichever
`refs/remotes/origin/main` the clone happened to have. When main advanced between the clone's
last fetch and a PR's measure time, every not-yet-anchored branch looked stale and re-woke a lane
for a re-anchor never owed — the `13e45a52 → 6ce5a2e4 → 3e016bf9 → d198d27e → f9715e3c →
031b652a → a9f05258 → 0717ab72a` churn and the #845 false-class. A verdict without a measured
sha could not distinguish "genuinely stale" from "measured against an outdated main".

## What changed

The gate now:

1. **Re-fetches the base's remote `main` freshly at measure time** — `git fetch <remote>
   +refs/heads/main:refs/remotes/<remote>/main`, where `<remote>` is derived from the base ref
   itself (`refs/remotes/origin/main`/`origin/main` → `origin`), so the fetched ref is exactly the
   compared ref. This is the same fetch the ci.yml guard step and the other PR gates already run,
   making the gate self-sufficient for every caller (worktree, rebase lane, `make check-pr-base`).
2. **Records the measured sha in every verdict** — a `measured against `<base>` at `<sha>` line on
   the OK and foreign-cut failure paths, so a FAILED is auditable at a glance and a stale measure
   is provable instead of assumed.
3. **Refuses on a failed fetch** (exit 1) — a stale measure must never pass, and a failed fetch
   must fail the gate, not fall back to a stale base ref.

`scripts/base_ref.py` is unchanged: `resolve_base()` already resolves a ref NAME and never
re-fetches (the correct division; the fresh fetch belongs to the gate itself).

## Tests

`tests/test_check_pr_base.py` gains the #1734 pins alongside the existing #845 cases:

- `test_stale_local_main_is_refreshed_before_the_verdict` — a deliberately stale
  `refs/remotes/origin/main` is re-fetched and the verdict measures against the live main sha.
- `test_a_fetch_failure_refuses_rather_than_passing_stale` — a fetch failure refuses, never passes.
- `test_a_missing_base_ref_is_restored_by_fetch_not_vice_versa` — a missing tracking ref is
  restored by the live fetch when the remote is reachable.

## Outcome

`check-pr-base` always states the main sha it measured at; a run whose local `origin/main` is
behind the API tip re-fetches first and judges against the fresh tip; a failed fetch fails the
gate rather than judging stale. Ship this in #1734, PR #1752.
