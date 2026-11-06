# Proposal — llgenie-pr-reviever's #1791-AC3 failing-job-log-read pointer (#1849 / #791)

The #1791-AC3 multi-lane rollout (#1849) requires every affected lane (implementer,
engine-improver, security, pr-reviever, pr-merge-conflict, ci-pipelines) to carry a
copy-or-pointer to the failing-job-log-read procedure in its own skill surface, versioned
per #791 (issue→PR under `agents/<lane>/`).

This lane (`llgenie-pr-reviever`) already enforces the read-the-failing-job-log-first
discipline in its SOUL and review procedure; the AC3 rollout needs it on the skill surface so
the pointer loads where this lane reads instructions. This change adds:

- a skill-surface pointer row in SKILL.md and a dedicated reference
  (`references/read-the-failing-job-log-pointer.md`) naming the implementer-lane canonical
  `red-bot-gate-read-the-failing-job-log.md` (merged via #1840);
- the change-note trio (agent-wiki row + docs/changes.d fragment + CHANGES.md row) per #1123;
- this openspec change so the `agents/`-touching diff satisfies
  `make check-pr-openspec-change` (#1807 presence half).

Pointer-only — no product code, no scripts, no workflow, no cross-lane edits (#791). Does not
close #1849: it is a single lane's vehicle; #1849 closes only when all five vehicles land and
merge.
