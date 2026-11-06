# Failing-job-log-read pointer in the engine-improver skill (#1791-AC3)

Vehicle: issue #1849 (agents(roles): #1791-AC3 fleet rollout). The engine-improver lane lands its
skill-surface pointer to the #1791 read-the-failing-job-log-first procedure, versioned per #791
(issue→PR under `agents/llgenie-engine-improver/`).

The lane's SOUL already carries the read-the-failing-job-log-first discipline verbatim (#1726 fleet
block); this vehicle — per the dispatch, a pointer addition, not a rewrite — makes the full mandatory
sequence loadable from this lane's skill surface:

- `agents/llgenie-engine-improver/skills/llgenie-engine-improver/references/read-the-failing-job-log-pointer.md`
  — new pointer reference naming the canonical procedure reference
  (`agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/red-bot-gate-read-the-failing-job-log.md`,
  merged via #1840) and pointing here for the full sequence, alongside this lane's own
  `engine-build-proof-dispatch.md`/`publish-run-adjudication.md` for the build-engine-specific loop.
- A SKILL.md pointer row in the proving/references section so the pointer is part of the skill surface.

No cross-lane file edits; the implementer's #1840 reference is named, not duplicated. SOUL line unchanged.
