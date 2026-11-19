# 2026-11-19 — the reconcile trigger carries its own PR-state re-read (issue #1749, PR #<TBD>)

Twice in one hour (2026-11-05) lanes described reconcile work for PRs the API already landed:
an "open #1742 at head `8482c24b`, failing guard job 126996060863, pending amend" while #1742 had
merged at 02:33:51Z (squash `ebabd9f1`, branch `fix/ci-verdict-skip-merged-pr-stragglers` deleted,
run 41951437719 all-green, zero amend/guard comments), and a repeated "open/unclaimed #1644" after
PR #1743 merged (squash `27d5477b`). The CI-side readers were already merged-aware (#897); the
leak is lane-side: post-merge straggler wakes and search-form board queries (`--state all`,
`gh search prs` without a state qualifier) hand a lane a PR-numbered red with no merged-aware
mapping.

## What was verified

- The leak channel measured live: `gh search prs --repo asimov-agent/llgenie '1644'` returns 8
  rows including CLOSED/MERGED (#1744, #1743, #2444, …) unless a state filter is applied — that
  is the phantom row's source; the wake channel needs the state re-read attached to the action.
- `scripts/pr_reconcile_guard.py` (new): reads `pulls/<n>` through `gh pr view --json` and prints
  exactly one verdict line — `#<n> merged, read-only (mergeCommit …)`, `#<n> closed, read-only …`,
  or `#<n> open, actionable (head …, mergeState=…, mergeable=…)`; a failed read prints no verdict
  and exits non-zero, so an unevidenced reconcile stays blocked. Shape note: `gh pr view` has no
  REST `merged` boolean — it normalizes `state` to OPEN/CLOSED/MERGED and prints `mergeCommit` as
  an object (measured, gh 2.104.0); merged is read from the state word plus a non-null `mergedAt`.
- The target: `make lane-reconcile-guard PR=<n> [REPO=<o>/<r>]` (mk/bots.mk, run by lanes from
  their own terminal; the script is proven in the unit battery, so it carries no host-only fixture
  entry — a fixture record would be stale by check-wiring's own rule — and it is documented in
  `docs/BOTS.md` under "The reconcile guard").
- Live proof at head `82a3b22c3` (2026-11-19): `PR=1742` → `merged, read-only (mergeCommit
  ebabd9f12e, merged 2026-11-05T02:33:51Z, head 8482c24b68)`; `PR=1743` → `merged, read-only
  (mergeCommit 27d5477b82)`; `PR=2913` → `closed, read-only`; `PR=2937` → `open, actionable
  (mergeState=DIRTY, mergeable=false)`; no `PR=` → usage error, non-zero.
- Tests: `tests/test_pr_reconcile_guard.py` drives the REAL script against a REAL fake-gh binary
  (the `test_resolve_run_pr.py` pattern) — merged/closed/open verdicts, the no-verdict read
  failures, the state-field pin, and the target/fixture/layer registration — 7 passed.
- Read-path text: new standing rule in `agents/standing-rules.md` ("a red carrying a PR number is
  not reconcile work until `pulls/<n>` says open"), the planner board-recipes
  (`llgenie-bot-orchestration`), the maintainer claim-check reference
  (`llgenie-pipeline-maintenance/references/verifying-planner-claims.md`), and the implementer
  claim reading (`llgenie-issue-to-pr`) all name the guard verdict before any reconcile action.

## Decision

- No new board VIEW was built: the repo's open-board queries already carry `--state open`
  (planner §2); the fix attaches the state re-read to the reconcile TRIGGER, where a merged row
  can still arrive through a wake, and retires phantom claims by naming the merge commit.

## Current status

OpenSpec change `board-read-path-phantoms` validated; all tasks ticked; PR opened against
`main` closing #1749.
