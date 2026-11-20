# orphan-commit-guard

## Why

Issue #442: a commit pushed to a branch after that branch's PR merged never reaches a PR, and nothing notices. Measured on #413: `feat/bot-model-1017`'s only PR (#410) merged at 11:00:47Z; the fix for #413 was committed to that same branch at 12:17Z — after the merge — so it sat invisible (no PR, no CI, no review) for a day while `main` kept failing. The pipeline has no step that notices a remote branch whose tip moved past every open-or-merged PR's head.

## What Changes

- NEW `scripts/check_orphan_commits.py` + make target `check-orphan-commits`: reads the merged-PR head map (`gh pr list --state merged --json number,headRefName,headRefOid,mergedAt`, reused from `bot_close_reasons.merged_pulls`), the open-PR head map, and every remote branch tip (`git ls-remote --heads origin`). A same-repo branch that is the source of a merged PR and whose current tip is NOT that PR's merged head, is not an ancestor of `origin/main`, and is not covered by an open PR, is an ORPHAN: each orphan commit is reported as `orphan: <branch> <sha> (merged PR #N, merged <time>) — <subject>` (one per line) and the run exits non-zero. Commit enumeration EXCLUDES patch-equivalent-to-main commits (`git cherry` patch-id): this repo squash-merges, so a commit whose patch already landed is not an orphan even though its sha never appears in main (measured on the first live sweep: 4 stale engine-bump branches — 3 genuinely undelivered bumps, strata's landed via squash under a different PR).
- NEW `data/orphan-baseline.json` + baseline tolerance in the guard: the first live sweep's 4 filed residues (consent-gated branch deletions, issue #442's "prerequisite for the gate's green baseline") are recorded as `(branch, merged PR number)` pairs; a matching residue is NAMED as a `tolerated baseline residue` and does not fail the run, while any orphan outside the baseline still fails. A branch re-cut by a NEW merged PR gets no shelter from an old entry.
- Folded into the existing CI guard gate (issue AC: "folded into an existing bot/CI gate"): a `make check-orphan-commits` step in the `ci.yml` guard job, which runs on PR lanes and on every push to `main` — so each merge re-checks the branch board.
- A test battery on a real local git repo (a merged-PR branch shape with a post-merge push) plus the established fake-`gh` PATH stub for the PR maps: orphan detected + named; no orphan when tips match merged heads; open-PR branch never flagged; residue equal to the merged head never flagged.
- `scripts/package-layers.json` gains the script's group membership; `docs/` gate list gains the target.

## Impact

- Affected specs: `orphan-commit-guard` (new capability)
- Affected code: `scripts/check_orphan_commits.py` (new), `tests/test_orphan_commits.py` (new), `mk/gates.mk`, `.github/workflows/ci.yml`, `scripts/package-layers.json`, `tests/test_ci_discipline.py` untouched (guard job already test-classified; `test_ci_unit_stage.py` untouched — the step joins the guard job, not `ci-unit`'s pinned 51-command sequence)

Not covered (separate issues, per AGENTS.md): none — the #442 body already scopes the branch-reuse cleanup to #441's shipped fix.
