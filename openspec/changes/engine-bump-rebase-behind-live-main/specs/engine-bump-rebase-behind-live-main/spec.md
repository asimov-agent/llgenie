# Engine-bump-rebase live-main comparison

## ADDED Requirements

### Requirement: pr_is_behind compares a PR against the LIVE main head, not a recorded base

The override `scripts/engine_bump_rebase.py::pr_is_behind` decides whether an open
`chore/engine-bump-*` PR must be forward-merged onto `main` before a merge is attempted. It MUST
compare the PR head against the **live upstream main head** (the `<remote>/main` ref the
workflow's checkout fetches, resolved by `upstream_main(repo)`), never against GitHub's recorded
`pr['base']['sha']`, because that recorded base is stale: for a genuinely-behind engine-bump PR
it is an older ancestor of the head (the #2266 shape: head `0a68b9ac` behind live main
`6f3d65b0` by 6, recorded base `49c63357`), which makes the compare API report `ahead` and skips
the very PR that should be rebased.

#### Scenario: a PR whose recorded base lags main but whose head lacks live main is BEHIND

Given an open engine-bump PR whose `pr['base']['sha']` is an older ancestor of its head, and
whose head does not contain the current live upstream main head,
when `pr_is_behind` evaluates the PR,
then it returns True (the PR is behind and must be forward-merged onto main).

#### Scenario: a PR whose head contains the live main head is NOT behind

Given an open engine-bump PR whose head contains the current live upstream main head
(or equals it),
when `pr_is_behind` evaluates the PR,
then it returns False (the PR is skipped).

#### Scenario: an unresolvable live main head is fail-closed BEHIND

Given `pr_is_behind` cannot resolve the live upstream main head (git `rev-parse` of the ref
fails or returns nothing),
when the decision is evaluated,
then it returns True (never skip on an unverifiable main head).

### Requirement: the claim and force-with-lease protocols are untouched

The rebase MUST still claim each PR before its push, re-read the live PR to refuse a dead vehicle,
release it after, and force-with-lease-push through the shared `sync_pr_with_main` — issues
#279/#285/#1733. Only the behind/not-behind decision's reference point changes.

#### Scenario: the claim protocol still guards a push

Given an open engine-bump PR that is behind the live main head,
when the rebase runs,
then it posts a claim comment before any push, refuses when the claim cannot be posted, re-reads
the live PR to refuse a closed/merged vehicle, and posts a done/gave-up marker after — the
`main()` flow is unchanged apart from the `pr_is_behind` reference point.
