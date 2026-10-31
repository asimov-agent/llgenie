# auto-merge now engages on a green docs-class completion, not only a CI run

- Issue: [#1227](https://github.com/asimov-agent/llgenie/issues/1227)
- OpenSpec change: `auto-merge-docs-class-trigger`
- Branch: `fix/1227-automerge-docs-class`

## What was wrong

A docs-only PR is structurally excluded from the auto-merge path. `ci.yml` strips the docs class at the
trigger by `paths-ignore` (issue #824), so a docs-only head never produces a `CI` run — but
`.github/workflows/auto-merge.yml` reacted to **only** the `CI` workflow completing
(`workflow_run: workflows: ["CI"]`). The docs gates (`lint`, `check-docs`, `check-wiring`,
`check-issue-bodies`, `openspec`) run in `ci-scope` (scope.yml), which carries no path filter, so a green
docs-class PR's only workflow_run is `ci-scope` completing — and no job watched it.

Measured on #1222 (head `10df36b8`, the shared census fix): armed
(`autoMergeRequest.enabledAt = 2026-10-31T19:51:07Z`), only `ci-scope`/`holds` runs at the head (both
green), yet every auto-merge sweep's `merge` job was `completed/skipped`. A green, armed, un-held docs PR
sat `BLOCKED / REVIEW_REQUIRED` forever with no lane able to clear it — not the review wall, the engine
never ran for it.

## What changed

- `.github/workflows/auto-merge.yml`: the `workflow_run` trigger now lists **`CI`** and the docs-class
  workflow (`ci-scope — selects the CI stages a diff needs, and runs the docs gates a docs-only PR still
  needs`, byte-identical to scope.yml's `name:` and to run-failure-reactor.yml's roster) — so a green
  docs-class completion opens the `merge` job too. The `merge` job's `if:` (`event == 'pull_request'` &&
  `conclusion == 'success'`) is unchanged, and `scripts/auto_merge.py` still re-reads the PR
  (`mergeable == MERGEABLE`, `mergeStateStatus == CLEAN`, head pinned, `do-not-merge` label FIRST) before
  it merges anything; a scope completion on a code PR merely fires the job EARLY, and it defers until the
  CI required-check is green. No gate is weakened (AC3).

## Verified

- `pytest tests/test_auto_merge.py tests/test_workflows_valid.py tests/test_resolve_run_pr.py
  tests/test_ci_scope_trigger.py` → 99 passed (incl. AC4 pin: a docs-class completion must engage the
  merge job, not only a `CI` run).

## Notes

- `workflow_run.workflows` matches the top-level `name:` verbatim (no wildcards, issue #463); a future
  rename of scope.yml's `name:` must update this list AND run-failure-reactor.yml's roster — the
  workflow-run gate (tests/test_workflows_valid.py) reds on either drift.
