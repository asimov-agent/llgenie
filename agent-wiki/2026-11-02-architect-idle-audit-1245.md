# Architect — add fleet idle continuous-improvement audit contract (#1245)

- **Issue:** #1245 (architect structural design)
- **Change:** new reference `agents/llgenie-architect/references/fleet-idle-audit.md` — canonical shape of the
  owner-approved idle continuous-improvement audit clause (trigger N=2, bounded one-pass, output = findings
  or "re-audited at sha"), with per-lane definitions for security, documentation-maintainer, ci-pipelines,
  engine-improver, reviewer. Concluded security definition on-record (comment 6551420026 on #1245).
- **Lane:** architecture. Structural cross-lane contract versioned under the architect lane via #791.
- **Status:** reference lands as part of #1245's collaboration contract; per-lane definitions may move to the
  owning lane's `agents/` tree when that lane folds them.
