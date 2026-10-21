# A green, conflict-free PR is merged by CI

- Issue: [#482](https://github.com/asimov-agent/llgenie/issues/482)
- OpenSpec change: `auto-merge-green-prs`
- Branch: `feat/auto-merge-green-prs`

## What changed

`.github/workflows/ci.yml` gains an `auto-merge` job, modelled on `trending-local-llms`'
`auto-merge` in `qa-validate.yml`:

- `needs: [guard, ci-images, linux, macos, engine-base, engine-matrix, engine-image, linux-published]`
  and `if: always() && !failure() && !cancelled()` — it cannot run early, and the push-only
  `engine-published-test` job being *skipped* on a PR does not block it;
- `pull_request` events only, non-draft, same-repo head, head branch not `main`;
- `make auto-merge PR=… REPO=… HEAD_SHA=…` → `scripts/auto_merge.py`, which reads ONE `gh pr view` and
  merges only when `state == OPEN`, `mergeable == MERGEABLE`, `mergeStateStatus == CLEAN`, the head is
  still the run's SHA, and no `do-not-merge` label is set. Everything else is printed and exited 0 — a
  deferral, never a failed run;
- `gh pr merge --squash --delete-branch --match-head-commit <sha>` under `secrets.BUMP_TOKEN` (the owner
  PAT; a merge with the job token starts no workflows, so the post-merge run on `main` would never run);
- then `make verify-closure PR=… REPO=…` (`scripts/verify_closure.py`) reads the merged PR's
  `closingIssuesReferences` and fails, naming the issue, when a claimed `closes #n` is still OPEN.

`AGENTS.md` rule 7 is rewritten to the new policy and the older "An APPROVED PR is merged" section is
reconciled with it, so the file states one rule: CI merges a green, conflict-free, same-repo, non-draft
PR; the agent never runs `gh pr merge` itself; `do-not-merge` is the human hold.

## Verified

- `pytest tests/test_auto_merge.py` → 14 passed (real `auto_merge`/`verify_closure` code against a real
  fake `gh` that records argv and flips to `MERGED` after a merge, plus the real `ci.yml`, `Makefile`,
  `README.md` and `AGENTS.md`).
- `python3 scripts/unit_tests.py argv` still lists the suite; `tests/test_auto_merge.py` is discovered.
- `make auto-merge PR=1 REPO=o/r HEAD_SHA=<sha> DRY=1` prints the decision and merges nothing;
  `make auto-merge … DRY=1` on a `DIRTY` fixture prints the conflict reason.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make check-pr-hygiene`, `make openspec-validate NAME=auto-merge-green-prs` — green.
- `make test-unit` — `4995 passed, 6 deselected in 872.16s (0:14:32)`, exit 0. The first run was red on
  `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` (its job-level `if:` whitelist), fixed by
  recording the auto-merge job as one documented scenario-scoped exception; `pytest tests/test_ci_images.py`
  → 26 passed and `pytest tests/test_auto_merge.py` → 14 passed after it.
- The `do-not-merge` label exists on the repo (`gh label list --search do-not-merge` → colour `#B60205`),
  so a reviewer can hold a PR the moment this lands.

## Notes

- Fork PRs are never auto-merged (the PAT cannot delete a fork branch); they stay manual, as in
  `trending-local-llms`.
- The `do-not-merge` label is the escape hatch: a reviewer labels a PR while reading it, and the next
  green run merges once the label is gone.
- **"Green" means every needed job SUCCEEDED**, not that none failed: the job requires
  `needs.<job>.result == 'success'` for all eight PR-relevant jobs, because a SKIPPED job (a matrix that
  collapsed, a job cancelled by a concurrency group) satisfies `!failure()` and would otherwise let the
  merge land a change the pipeline never ran. `pytest tests/test_auto_merge.py` asserts every one of
  those guards, and `make check-workflows` keeps the YAML parseable.
- The job's merge state read is one `gh pr view` call (`--json
  state,isDraft,mergeable,mergeStateStatus,headRefOid,labels`), so a deferred run costs one API call.
