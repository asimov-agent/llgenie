# Spec delta: reuse-agent-leg

## REMOVED Requirements

### Requirement: a reusable agent-leg workflow exists
**Reason:** the reusable workflow `.github/workflows/agent-leg.yml` was born orphaned —
no workflow ever called `workflows/agent-leg.yml`; every agent leg migrated to the
composite action `./.github/actions/agent-leg`, which is the single code path for the
ordered preflight. A `workflow_call`-only file with zero callers is dead machinery that
the workflow gates still validate and pin as if live (issue #2443).
**Migration:** none needed. All six agent legs already call the composite action; the
composite action is unchanged by this change. The removed file lives in git history
(`origin/main`) if a whole-job reusable workflow is ever wanted again.
