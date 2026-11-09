# engine-bump-rebase compares against the LIVE main head, not a stale recorded base (issue #2383)

## What changed

`scripts/engine_bump_rebase.py::pr_is_behind` decided whether an open engine-bump PR was behind
`main` by comparing GitHub's **recorded** `pr['base']['sha']` with the PR head through the
compare API. For a genuinely stale engine-bump PR (the #2266 shape: head `0a68b9ac` lacks
current main `6f3d65b0` by 6 commits) GitHub records the `base.sha` as an **older ancestor** of
the head (`49c63357`), so the compare API reported `ahead` and the workflow logged "not behind
main — skip". A re-dispatch at main `6f3d65b0` (run 42590303393) skipped #2266 and rebased only
the three fix/ PRs.

The fix resolves the **live upstream main head** — the `<remote>/main` ref the workflow's own
checkout fetches (`upstream_main(repo)`, the same ref `sync_pr_with_main` forward-merges onto) —
and compares the PR head against THAT, never GitHub's stale recorded `pr['base']['sha']`. If the
live main head cannot be resolved, it fails closed to `behind` (never skip). A head that contains
the live main head is skipped; a head that lacks it is forward-merged.

## How it was verified

- New unit test `test_stale_recorded_base_but_head_behind_live_main_is_behind` reproduces the
  #2266 shape (recorded base `b*40` stale; live main `m*40`; head `h*40`) and asserts `pr_is_behind`
  returns True AND that the compare path used the live main head, never the recorded base.
- `test_unresolvable_live_main_is_fail_closed_behind` — a `rev-parse` that fails returns True.
- `tests/test_engine_bump_rebase.py` green (20/20); full `make test-unit` green.
- `make openspec-validate NAME=engine-bump-rebase-behind-live-main` exit 0.
- The guard, claim (#279/#285) and dead-vehicle force-with-lease (#1733) protocols are unchanged —
  only the behind/not-behind reference point moved.

## Decision

`engine-bump-rebase` keeps every open `chore/engine-bump-*` PR current with the live main head,
so a reviewer sees a mergeable-fresh branch instead of a stale base that only surfaces at merge
time. #1484's acceptance #2 ("a behind engine-bump PR is forward-merged to main head") becomes
actually true; a re-dispatch of the workflow is the re-verify evidence.

Issue: #2383
