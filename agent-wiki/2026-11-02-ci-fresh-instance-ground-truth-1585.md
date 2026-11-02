# 2026-11-02 CI fresh instance is the ground truth (issue #1585)

Issue **#1585** (planner-framed; this lane's repo-side deliverable, via #791).

## What changed

The pipeline-maintainer lane's tree now carries a ground-truth contract at
`agents/llgenie-ci-pipelines-maintainer/skills/llgenie-pipeline-maintenance/references/ci-fresh-instance-ground-truth.md`
mirroring the planner's live `references/ci-fresh-instance-ground-truth.md` doctrine (the #1584 case).

The rule it codifies: verdicts come from CI's **fresh instance** (a `pull_request` run id + head
sha), never from a lane's local read on the shared host. A lane that holds a red/green verdict on a
local `make check-*` run — while CI's fresh run shows the opposite — is violating the standing
contract. Diagnose a red from the failing job's own log line before concluding product-vs-infra; a
rerun that re-reds on the identical gate is a deterministic product red (dispatch the fix, never
relabel infra); re-measure the judged head via the `upstream/main` merge-base; and when a PR's
head-shape is disputed, publish GitHub-API re-measurements (pull `.head.sha`, both remotes'
`ls-remote`, `compare/<base>...<head>`) rather than re-arguing a stale-sha description.

It also codifies acceptance #4: assert with **subset** forms (`expected <= set(actual)`), never
exact-set equality, so a test/roster/manifest assertion catches the regressions it owns without
freezing the set against the next legitimate addition.

## Behavioural surface

This is the tree-side contract binding this lane (references live under
`agents/<lane>//skills/.../references/`, changed by issue + PR per #791). The rule gates how this
lane reports, holds, and merges: every verdict it states must cite a CI run id + sha.
