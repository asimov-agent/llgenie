# Proposal: board read-path drops merged/closed PRs and guards every reconcile with a state re-read

## Why

Twice in one hour (2026-11-05) bot lanes presented live reconcile objects that the GitHub API
says do not exist: an "open #1742 at head 8482c24b with failing guard job, pending amend" (#1742
merged 02:33:51Z, squash `ebabd9f1`, branch deleted, zero amend/guard comments, run 41951437719
all-green) and an "open/unclaimed #1644" (closed 03:20:47Z via merged PR #1743, squash `27d5477b`).
Both lanes measured the live API and agreed the objects were absent; the phantom came from the
board-read *before* their own re-measure. GitHub issue: #1749.

The channel, identified at this implementation (2026-11-19, gh 2.104.0):

1. **post-merge straggler wakes**: `workflow_run`-style wake-ups hand a lane a failed run on a
   branch whose PR already merged. The repo's own CI readers skip this class (`ci_verdict.py`
   `merged_pr_run`, `resolve_run_pr.py` `landed_pr_for_head`, both merged-aware), but a lane woken
   with only a run/branch has no merged-aware mapping and infers "open PR, red, reconcile".
2. **lane-side board recipes that return merged rows state-blind**: measured live —
   `gh search prs --repo asimov-agent/llgenie '1644'` returns `1743 merged, 1744 closed, …`; a
   search-form read that asks no `state` field (or `--state all`, used for vehicle sweeps) hands the
   lane a merged row that looks exactly like open work. Every script scanner in this repo already
   filters `state=open` (`open_prs` in `worktree_report.py`, `fix_bot_sweep.py`, `arm_auto_merge.py`,
   `check_arms.py`) — the leak is the recipe text the agent skills carry, not the scripts.

The recurring cost: planner cycles certifying empty reconciles, and the standing risk of a lane
acting on a phantom (push to a deleted branch, edit a merged body, re-open a closed issue).

## What Changes

- **A shared reconcile guard** — new `scripts/pr_reconcile_guard.py` + `make lane-reconcile-guard
  PR=<n> [REPO=…]`: the one instrument a lane calls BEFORE any reconcile action on a PR-numbered
  red. It reads `pulls/<n>` (`state`, `merged`, `mergedAt`, `mergeCommitSha`, `headRefOid`,
  `mergeable`) and prints a one-line verdict: `#<n> merged, read-only …` / `#<n> closed, read-only …`
  / `#<n> open, actionable …` (host-only target; lanes run it from their own terminal).
- **Board-read recipes carry state** — the lane-facing recipe texts (planner board cadence,
  planner lane-claim verification, maintainer planner-claim verification, issse-implementer claim
  reading) gain the rule: an open-work query SHALL name `is:open`/read `.state` per row, and a row
  that names a merged/closed PR is never reconcile work — call the guard, emit "merged, read-only".
- **A standing rule** in `agents/standing-rules.md`: reconcile-trigger re-verify (the guard is part
  of the trigger, not a reactive ask).
- **Tests** `tests/test_pr_reconcile_guard.py` prove the three verdicts + the merged read-only refusal
  against a fake-gh fixture (the `test_resolve_run_pr.py` pattern).
- `scripts/package-layers.json` registers the module; `tests/fixtures/host-only-wiring.json` records
  the host-only target; `docs/BOTS.md` documents it; agent-wiki entry + changes fragment + CHANGES.md.
- Verification AC: re-run the guard live against #1742 and #1743 — neither surfaces as open work.

## Impact

- Affected specs: none existed for the board read path; this change adds `lanes-board-read`.
- Affected code: `scripts/pr_reconcile_guard.py` (new), `mk/bots.mk`, `Makefile` roster,
  `scripts/package-layers.json`, `tests/fixtures/host-only-wiring.json`, `tests/test_pr_reconcile_guard.py` (new).
- Affected agent tree: `agents/standing-rules.md`, planner + ci-pipelines-maintainer +
  llgenie-issse-implementer skill references (synced with `make sync-agent-profile`).
- No new CI job; no workflow changes. GitHub issue #1749 is the root; PR closes it.
