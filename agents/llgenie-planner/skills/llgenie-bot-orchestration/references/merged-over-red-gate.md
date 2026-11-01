# Merged-over-red: verify a merge on the HEAD check-set, never mergeStateStatus

An llgenie PR can be MERGED (by the owner) while its **head-instance** check-set is red.
The merge-commit re-run sometimes clears it; when it doesn't, a red defect ships to `main`
(the #1382 class: 3 `test_agent_profiles.py` failures landed on main).

Measured instances: #1385 (merged `e91b42c9`, head `65fdf69b` = `ci-verdict`/`scope`/`guard`
failure + `linux` skipped; cleared only by merge re-run `41320696487`), #1374 (merged
`fd3efd67`, head `7ebff155` = `linux/unit` + `ci-verdict` failure), and the documented
#1309-#1321 range.

## Rule

Verify a merge **on the head-instance check-set**, not on `mergeStateStatus` and not on the
merge event (its `skipped`/`cancelled` semantics are the trap — `gh pr checks`'s `fail`
column lies about cancelled; a fully-green check list can still be `BLOCKED`/`REVIEW_REQUIRED`).

- Read: `GET /repos/{owner}/{repo}/commits/{head_sha}/check-runs` (the PR's head sha, not the merge sha).
- A head whose `ci-verdict` or `linux/unit` is anything but `success` was NOT gated green — even if closed.
- When you find a merged-red, measure the acceptance criteria **on `main` at the merge tip**, not on the PR diff (the diff is now main's).

A persistent `make` merge-gate check enforcing this is tracked as issue #1386 (CI-pipelines lane).

## "The tip is red" — bind every failing run to its `head_sha` first

At a merge-commit tip, two different things can look like "main is red" and they need opposite handling.
Resolve each failing run's `head_sha` before concluding anything:

```bash
TIP=$(git rev-parse origin/main)
gh api "repos/<o>/<r>/actions/runs?head_sha=$TIP&per_page=20" \
  --jq '.workflow_runs[]|{name,id,databaseId,status,conclusion,head_sha}'
# for any failing id: is its head_sha actually the tip?
gh api repos/<o>/<r>/actions/runs/<id> --jq '{name,event,head_sha,conclusion}'
```

- **A `ci-verdict` run whose `head_sha` is an older, pre-merge PR head** is a post-merge RECHECK of that
  merged PR's own CI (the #1309-latitude pattern), not evidence the tip is bad. It re-evaluates the
  triggering run's head, so it keeps failing on a head the merge already superseded — report it as
  "recheck of `<old head>`, already handled", never as a fresh main red, and never file it.
- **The tip's OWN `ci.yml` run failing concrete jobs** (`linux/lint` at `make ci-lint`, `linux/openspec`
  at `make ci-openspec`) is a genuine red that needs an incident. Name the failing **step** from the jobs
  payload (see `verifying-lane-claims.md` §7 — never grep the raw log), then check whether the cause
  predates the most recent merges: `git merge-base --is-ancestor <suspect-commit> origin/main` plus a
  local reproduction of the named gate (e.g. `make check-docs`) separates "newly broken" from "has been
  red since the gate landed, and nobody filed it".
- A red that is pre-existing but untracked is still your incident to file — "it predates today's merges"
  is attribution, not an excuse. Route it to the lane owning the failing surface (docs-alignment gate →
  documentation lane; workflow/gate design → ci-pipelines), with the run id, the failing job+step, and
  the commit that introduced it.
