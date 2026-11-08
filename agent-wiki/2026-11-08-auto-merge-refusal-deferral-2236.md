# a merge GitHub refuses at the instant of `gh pr merge` defers or succeeds, never dies red (issue #2236) — 2026-11-08

**Implements:** issue #2236 — the auto-merge `merge` job died red when `gh pr merge` was refused the instant
it ran, and nothing repaired it. The merge machinery itself reddening is how green PRs stop landing while
the board reads "waits on approval".

Measured specimen — PR #2102, run `42469582901`, head `55d0623a0626`: the job read the PR `CLEAN`, called
`gh pr merge`, and GitHub answered `GraphQL: Pull Request is not mergeable (mergePullRequest)` because a
sibling auto-merge run had already MERGED #2102 a second earlier (`mergedAt 10:01:04Z`, refusal at
`10:01:05Z`). `_merge()` — the plain-`CLEAN` path and the post-approval path in `_clear_review` — called
`merge()` unguarded, so the `SystemExit` propagated to the top and exited 2. The admin/verdict paths already
honoured the gate's own contract ("a refusal is a deferral with the reason on the PR, never a red run");
these were the two paths that lacked it.

## What changed

- **`scripts/auto_merge.py`** — `_merge()` now wraps `merge()` in `try/except SystemExit`. On a refusal it
  re-reads the PR: already `MERGED` → a sibling landed it, so this run is SUCCESS (verify the closure),
  never red, and there is nothing to defer; still `OPEN` → defer with the refusal reason **on the PR**,
  exit 0. Never a red pipeline either way.
- **`docs/BOTS.md`** — two new decision-table rows: a refusal from a concurrent sibling merge is success
  (issue #2236), and a refusal while the PR is still open defers to a human with the reason on the PR.
- **Tests** — `tests/test_auto_merge.py`: 95 passed (92 prior + 3 new), including the negative control
  `test_a_merge_refused_while_still_open_defers_naming_it`, which reds if the fix swallows a genuine
  refusal without deferring (a bare `return 0` leaves the PR silently stranded). The 3 new tests fail on
  the old tree and pass on the new.

## Decisions

- **A refusal is a deferral, never a red run.** The gate treats a concurrent-merge `MERGED` re-read as
  SUCCESS (the sibling already landed it; re-verifying the closure is the only residue), and an
  `OPEN` PR refusal as a defer to a human. A red run repairs nothing and reads as "waits on approval".
- **Re-read the PR before judging the refusal.** A bare `return 0` on `SystemExit` would strand a PR whose
  refusal was real; the re-read tells MERGED (done) apart from OPEN (defer).

Refs: #2236 (this issue), #2102 (the specimen PR), #934 (one row per changes.d file).
