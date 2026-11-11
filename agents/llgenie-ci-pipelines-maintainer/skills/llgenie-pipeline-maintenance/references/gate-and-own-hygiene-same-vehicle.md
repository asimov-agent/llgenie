# A gate fix and its own hygiene test must land on the same vehicle (#1592/#1591)

Measured 2026-11-02 on #1588/#1591/#1592 (squash `8f66676e` on main).

## The failure mode

A fix that removes the OLD shape a producer convention asserted must reword that assertion **in the same
PR**, or the fix's own CI reds it. #1592's engine-bump.yml change dropped the generated commit's `Issue:`
prefix; `tests/test_pr_hygiene.py::test_this_repositorys_producers_state_the_issue_the_fix_and_the_benefit`
still required a literal `Issue:` in every producer's workflow text, so `linux/unit` red on the PR that
removed it. The planner caught it; the reword landed as a second commit on the same branch.

## The corrected invariant

- `engine-bump.yml` is a **rolling pin chore that claims no issue** — it must carry `Fix:`/`Benefit:`/
  `Technical:` + the explicit `closes no issue` marker, and must NOT carry a capital `Issue:` substring.
- Every other producer stays **strict on all four parts** (`Issue:`+`Fix:`+`Benefit:`+`Technical:`).
- Guard-proof both directions before pushing: plant the old wording → test reds (asserts the missing
  `closes no issue` / the forbidden `Issue:`); restore → green.
- Note the `# Issue #107:` header comment is safe — it lacks the capital-colon `Issue:` substring.

## Main advances faster than the job queue — check-pr-base reds on a cut-from-old cancel

`origin/main` advanced three times during one PR's lifetime (febd9646 → 99874a46 → bf44197d). The guard
leg may pass at run start, then `linux/unit` re-runs `check-pr-base` minutes later and reds because the
merge-base with `origin/main` is no longer `origin/main` itself (issue #845).

- Rebase **onto the live canonical `upstream/main` tip** (`git fetch upstream main; git rebase --onto
  upstream/main <old-base>`), and confirm `git merge-base upstream/main HEAD == upstream/main`.
- Push with `--force-with-lease origin <branch>` after fetching the remote tip (the rebase above made the old remote tip a non-ancestor, so `--force-if-includes` is not used) — a
  same-vehicle force-push on your own branch is the authorised correction.
- The fresh `synchronize` event also carries the corrected PR body, which is how the #1589 event-snapshot
  stale-body red clears.

## Delivery discipline

- Finding issue and fix PR are **separate vehicles** (finding #1591, fix #1592) — a fix PR as the only
  record of the finding is wrong.
- `closes #1591` in the PR body auto-closes the issue on merge (measured 15:11:20Z).
- The repo's own auto-merge lands a fully green PR (`mergedBy=asimov-agent`); the lane never merges/arms.
- Verify the squash is an ancestor of main before declaring done.
