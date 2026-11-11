# Retire the orphan reusable agent-leg workflow (issue #2443, PR #)

`make code-review-scan` found `.github/workflows/agent-leg.yml` orphaned: `workflow_call`
is its only trigger and no workflow references `workflows/agent-leg.yml`. The reusable
half of #798's `reuse-agent-leg` shipped, but the migration consumed it through the
COMPOSITE ACTION instead — all six agent legs call `./.github/actions/agent-leg`
(measured at `origin/main@ac0cd6736`: architecture-bot, fix-bot, issue-bot,
issue-refiner, rebase-bot, registry-sync-review). The workflow was born with no caller.

## Decision

Delete the workflow and its `workflow-run-exemptions.json` entry together. The composite
action is already the single code path for the ordered preflight (the one-code-path rule
the finding itself invoked); a `workflow_call`-only file with zero callers is dead
machinery the gates still validate and pin. Removing the workflow alone REDS
`make check-workflows` ("exempts a workflow that does not exist: 'agent-leg — the
reusable agent leg'") — the exemption retires with the workflow.

## Verified

- `make code-review-scan` after the delete: **no findings** — the
  `reusable-orphan/agent-leg.yml` key is gone.
- `make check-workflows`, `make check-wiring`, `make lint` green on the branch.
- OpenSpec `retire-orphan-reusable-leg` validates: REMOVES "a reusable agent-leg
  workflow exists" with a migration note; the composite-action requirement is untouched.

## Current status

Branch `fix/2443-retire-agent-leg-reusable` → PR closes #2443. The workflow file lives in
git history (`origin/main`) if a whole-job reusable leg is ever wanted again.
