# llgenie-ci-pipelines-maintainer — #1791-AC3: the read-the-failing-job-log sequence lands a skill-surface pointer

- **Date:** 2026-11-06 · **Issue:** #1849 (the five-lane #1791-AC3 rollout, this lane = ci-pipelines), parent #1791-AC3
- **Base:** `upstream/main` `888e879a` · **Branch:** `fix/1849-ci-pipelines-failing-job-log`

## The gap

#1791-AC3 requires each affected lane (implementer, engine-improver, security, pr-reviever,
pr-merge-conflict, **ci-pipelines**) to carry a copy or a pointer to the read-the-failing-job-log-first
procedure **in its own skill**, versioned per #791. PR #1840 ships the implementer's copy/pointer only.
This lane's SOUL.md already carried the discipline verbatim (line 92, from #1726), but the grep for
`red-bot-gate|failing-job-log|failing job` matched **SOUL.md only — NOT this lane's skill surface**
(`agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/`). So the sequence was
not loadable where the lane loads instructions — its own skill (#791).

## What this vehicle changes

- `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/red-bot-gate-read-the-failing-job-log.md`
  (new) — a local pointer reference naming the canonical cross-lane procedure and the rule.
- `agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/SKILL.md` — one `When to
  Use>` pointer row so the reference is discoverable from the skill a lane loads, matching how the other
  references are wired. The SOUL line (line 92) is kept untouched — this is a **pointer addition, not a
  rewrite**.

Text-only under the lane dir + change-note trio; no CI gate, test, workflow, product code or other
lane's files touched. The canonical procedure file itself lives in the implementer lane
(`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`)
and is named by this lane's pointer; it is verified at the merged head once #1840 merges.

## Proof

`git show HEAD:agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/SKILL.md | grep red-bot`
now returns the pointer row, and `ls .../references/red-bot-gate-read-the-failing-job-log.md` returns the
new reference. `check-docs`, the SYNC-verification (`sync-agent-profile PROFILE=llgenie-ci-pipelines-maintainer CHECK=1`),
and the change-note pair (this note + `docs/changes.d/2026-11-06-ci-pipelines-read-the-failing-job-log.md`)
are the gate evidence.

## Out of scope

The other four lanes' vehicles, the canonical reference's own content (implementer-owned), and any
SOUL/skill rewrite — this is the ci-pipelines #791 pointer vehicle. No merge (#1088).
