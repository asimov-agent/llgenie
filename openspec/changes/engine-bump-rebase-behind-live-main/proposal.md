# engine-bump-rebase compares a PR against the LIVE main head, not a stale recorded base

## Why

`scripts/engine_bump_rebase.py::pr_is_behind` decides whether an open engine-bump PR must be
forward-merged onto `main` by comparing GitHub's **recorded** `pr['base']['sha']` with the PR
head through the compare API. For a genuinely stale engine-bump PR (the #2266 shape: head
`0a68b9ac` lacks current main `6f3d65b0` by 6 commits) GitHub records the `base.sha` as an
**older ancestor** of the head (`49c63357`), so the compare API reports `ahead` and the workflow
logs "not behind main — skip" — the one PR a reviewer actually needs current is the one most
likely to be skipped. Acceptance #2 of the `engine-bump-rebase-ci` change ("a behind engine-bump
PR is forward-merged to main head") was false while this stood; a re-dispatch at main
`6f3d65b0` (run 42590303393) skipped #2266 and rebased only the three fix/ PRs.

## What changes

`pr_is_behind(pr, repo, run_git)` resolves the **live upstream main head** — the `<remote>/main`
ref the workflow's own checkout fetched (`upstream_main(repo)`, the ref `sync_pr_with_main`
forward-merges onto) — and compares the PR head against THAT, never GitHub's possibly-stale
recorded `pr['base']['sha']`. If the live main head cannot be resolved, fail closed to `behind`
(never skip). A PR whose head contains the live main head is `not behind` → skip; a head that
lacks it is `behind` → forward-merge. The guard, claim and force-with-lease protocols (issues
#279/#285/#1733) are untouched — only the behind/not-behind decision's reference point changes.

## Who

`llgenie-ci-pipelines-maintainer` (this lane owns scripts/workflows/gates, precedence #2073).
