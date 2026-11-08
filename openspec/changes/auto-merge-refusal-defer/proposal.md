# A merge GitHub refuses at the instant of `gh pr merge` defers or succeeds, never dies red

## Why

auto-merge's `_merge()` called `merge()` unguarded on the plain-CLEAN path and on the
post-approval path in `_clear_review`, so a `SystemExit` raised by a merge GitHub refuses at
that instant propagated to the top and died the job red. The gate's refusal contract — "a
refusal is a deferral with the reason on the PR, never a red run" — was already honoured by
the admin and verdict paths; these two were the gap.

Measured: run `42469582901` read PR `#2102` CLEAN and called `gh pr merge` at `10:01:05Z`;
GitHub answered `Pull Request is not mergeable (mergePullRequest)` because a sibling auto-merge
run had **already merged `#2102` at `10:01:04Z`**. The `SystemExit` propagated, the `merge`
job died red, and the board read "waits on approval" while nothing waited. A concurrent merge
(or a transient async recompute) can move the PR between this run's own `pr view` and the
merge call, so a CLEAN read is never a licence to let a refusal die red.

## What Changes

- **`scripts/auto_merge.py` — `_merge()`**: wrap `merge()` in `try/except SystemExit`. On a
  refusal, re-read the PR:
  - already `MERGED` → a sibling landed it, so **this run is success** (verify the closure),
    never red, and there is nothing to defer;
  - still `OPEN` → the refusal is real, so **defer with the refusal reason ON the PR**, exit 0.
- **`docs/BOTS.md`**: two decision-table rows document the rule (already-`MERGED` → verify
  closure as success; still-`OPEN` → defer with the reason on the PR).
- **`tests/test_auto_merge.py`**: three new tests pin the behaviour, including the negative
  control (a still-open refusal must defer, never be swallowed by a bare success return).

## Impact

- A green PR that a sibling auto-merge run just landed no longer sends the merging job red.
- A genuine refusal (still-OPEN) still defers with its reason on the PR, so a swallowed-return
  bug cannot silently strand a PR.
- The merge gate's refusal contract is uniform across the plain-CLEAN, post-approval, admin and
  verdict paths, not three of four.
