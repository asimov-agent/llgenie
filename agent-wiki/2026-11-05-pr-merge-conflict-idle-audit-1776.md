# LLGenie PR Rebase Conflicts: empty-queue own-domain audit clause (owner 2026-11-01, #1245, #1776)

Folds the continuous-improvement contract's per-lane clause for this lane (structuring issue #1245; the
planner's fleet-wide contract is versioned in its SOUL; the per-lane fold follows the ci-pipelines #1278
pattern). This lane is triggered by CONFLICTING/DIRTY or stale-base dispatches and had no loop that produced its
own next issue when the queue was empty — a barren lane simply idled.

## What changed

- `agents/llgenie-pr-merge-conflict/SOUL.md` — new bullet under the lane rules (kept outside the fleet
  block): an empty reactive queue for N=2 consecutive passes is one bounded own-domain audit, not an idle
  pass. This lane's audit definition: **rebase-process gaps** (which stale-base or conflicted PRs reach the
  board as `BLOCKED` / `DIRTY` with no tracked remediation, fork-headed PRs whose base can no longer be
  replayed, one-vehicle violations). Findings filed as six-section `agent:implement` issues routed through
  the normal queue — never implemented by this lane's own pass (this lane does not implement beyond its own
  skill/behaviour and its rebase remit); otherwise record `re-audited at <sha>, no findings`. One-pass scope,
  no infinite loop; never overrides reactive work. (`#791 #1245`)
- `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md` — matching
  "Empty-queue own-domain audit (2026-11-01, #1245, #1776)" section with the same clause.

## Verification

- `make check-docs` + `make lint` green at the PR head (change-note pair ships in the same PR, #1123).
- Change-note fragment + agent-wiki note index into `CHANGES.md` via `make changes-index` (never hand-edit).
- PR authored by this lane, closes #1776; merge owner-gated (#1088).
