# Proposal: arms-gate-queue-semantics

## Why

Issue #2378. The arms gate (`scripts/check_arms.py`, consumed by `arms.yml` daily at 01:13 UTC) reads rule 16
as: every open, non-draft, mergeable, default-based PR must carry `autoMergeRequest`. Measured at main
`2f6574ea8`: a local `python3 scripts/check_arms.py check` flags **4 of 4 open PRs** — every lane mid-CI,
mergeable only because GitHub precomputes `mergeable=MERGEABLE` while checks run. The scheduled arms run
43181777316 (job 129043889459) is the red this tracker dedupes on, and it will re-fire on every healthy board
forever: the agent lane is FORBIDDEN from running `gh pr merge` (AGENTS.md: "CI merges a green, conflict-free
PR; the agent never merges it by hand"), so `autoMergeRequest` can never be the accepted form — the lane's
queue entry is the CI `auto-merge` job's hold, `mergeStateStatus == CLEAN`. The gate therefore has no
definition under which a healthy agent-driven board is green: it flags in-flight work (checks not terminal,
review chain mid-approval) and already-queued work alike.

## What Changes

- **Finished gets a check verdict.** A PR is *finished* only when its `statusCheckRollup` is terminal and
  GREEN (all rows COMPLETED, none FAILURE/CANCELLED/TIMED_OUT/START_FAILURE). Rows still QUEUED/IN_PROGRESS,
  an empty rollup, or a RED rollup mean work in progress — skipped, not flagged (CI already names a red PR).
- **The merge queue counts as armed.** `mergeStateStatus == CLEAN` (green + conflict-free — the CI auto-merge
  job lands it) satisfies rule 16 exactly like `autoMergeRequest != null` does today.
- **An in-flight review chain is not finished work.** `reviewDecision` REVIEW_REQUIRED/CHANGES_REQUESTED means
  the lane's verdict chain (CI → code-review-bot → approval → CLEAN) has not landed; the alarm must not
  preempt it.
- **Rule 16 keeps its teeth.** A PR that is green, mergeable, non-draft, default-based, review chain complete,
  yet neither armed nor CLEAN-queued — green-but-BLOCKED-after-approval, or green-but-BEHIND (the auto-merge
  job refuses BEHIND) — remains a named finding.
- `report` prints one explicit state per open PR (`armed / queued / in-flight / in-CI / red / finding`) so the
  board audit is self-describing; the unfiltered single `gh pr list --json` call (#1021) now carries
  `mergeStateStatus,reviewDecision,statusCheckRollup`.

## Impact

Affected specs: `merge-lane-arms` (the arms gate audit). Affected code: `scripts/check_arms.py`,
`tests/test_arms.py`, `.github/workflows/arms.yml` (header comments + step name only; no trigger/permission
change). No Makefile change (`make check-arms` unchanged).
