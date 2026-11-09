# engine-bump-rebase compares against the LIVE main head (issue #2383)

2026-11-09 · issue #2383 · PR #2396

## What changed

`scripts/engine_bump_rebase.py::pr_is_behind` compared a PR head against
GitHub's recorded `pr['base']['sha']` — the PR's base at creation or last
base-change, not the current main head. A genuinely-behind `chore/engine-bump-*`
PR whose recorded base is an old ancestor of main read "ahead" against that stale
base and was **skipped** ("not behind main — skip"), exactly the PR the workflow
was built to keep fresh.

Measured in verification of #1484 (run 42590303393, head `6f3d65b0`): PR #2266's
head `0a68b9ac` is behind current main by 6 commits
(`compare/6f3d65b0...0a68b9ac` → `diverged`, `behind_by: 6`), but its recorded
base `49c63357` lags main, so the old `pr_is_behind` returned False and the PR
was skipped.

## How

- `live_main_head(repo)` resolves the LIVE upstream main head from the checkout:
  `upstream_main(repo)` (the `<upstream>/main` ref the workflow fetches in its
  `fetch-depth: 0` checkout, resolved by remote URL per issue #206) +
  `git rev-parse --verify`.
- `pr_is_behind(pr, repo)` compares the PR head against that live sha via the
  compare API. A head that does not contain the live main head is behind →
  rebased; one that contains it is not behind → skipped.
- An unresolvable live main head fails **closed to behind** (a possibly-behind
  PR is never skipped because a local ref could not be read).
- The force-with-lease/claim protocol and the dead-vehicle guard (#279/#285/
  #1733) are untouched.
- `tests/test_engine_bump_rebase.py`: the compare path asserts the **live main
  sha** is the base side; new `test_compares_against_live_main_head_not_the_
  recorded_base` locks the #2266 stale-recorded-base-but-behind classification;
  `test_unresolvable_live_main_is_behind` locks the fail-closed path. The new
  stale-base test REDS against the pre-fix `pr_is_behind` (negative control).

## Verified

- `docker run … llgenie/test:latest python -m pytest tests/test_engine_bump_
  rebase.py` → 20 passed.
- Full `make test-unit` (containerized, 229 files) → 3505 passed, 0 failed.
- `make bot-preflight` measures origin/main at `19d30772` (92544 b / 1373 l of
  AGENTS.md).
