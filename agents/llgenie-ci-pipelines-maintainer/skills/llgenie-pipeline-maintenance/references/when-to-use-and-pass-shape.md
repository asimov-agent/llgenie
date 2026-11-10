# When to Use

> Hygiene: `references/repo-artifact-conventions.md`

> Rollups/polling/arming: `references/monitoring-check-rollups.md`
> A red verdict with otherwise-green jobs is re-judged, never re-rolled; an expired run's verdict is trapped (fresh run, not re-judge): `references/ci-verdict-rejudge-and-expiry.md`
> A main-tip verdict: cite `ci-scope NO VERDICT` (genuine failure, #2221) vs `UNJUDGED RED` (own-workflow rows) as two layers — fix/measure: `references/ci-verdict-own-surface-vs-unaccounted.md`
> Tree parity vs live: `references/verifying-agent-tree-parity.md`
> Planner claims a branch/run/merge is missing — re-measure canonically first: `references/verifying-planner-claims.md`

> "Is this leg slow or stuck?" — build the duration band from completed JOBS (p50/p95 + run ids), re-measure any figure an issue quotes, and set the floor at ~2× p95: `references/measuring-job-duration-bands.md`

> A job that ended `cancelled` at its `timeout-minutes` wall with no test summary is **UNTESTED, never green** — usually a live-network stall, not a failing test. See `references/diagnosing-cancelled-runs.md`.

> A red is a verdict, not a cause — on any red bot-gate, read the failing job's OWN log and quote the failing step (run id + job id + head sha) before ANY dispatch or green/red/reviewable claim. Pointer to the canonical cross-lane sequence (implementer lane, PR #1840, required by #1791-AC3): `references/red-bot-gate-read-the-failing-job-log.md`.

> Re-pointing a PR's closing issue: amend the commit's `closes #N` too, not just body/title — see `references/pr-issue-linking-and-force-push.md`.

The task is "do the pipelines at https://github.com/asimov-agent/llgenie/actions still do what they say". Use this for the audit loop (measure intent vs reality, file the gap, fix it behind a reviewable
PR) — not for writing a normal feature (the repo's `AGENTS.md` owns that).

**Scope is the MONITOR loop: watch pipelines from the PRs, read the LOGS, and report every red to the inbox so it decides (owner instruction 2026-10-30).** This lane is always running: it watches the open PRs' CI runs, and for every red it reads the failing job's LOG (the actual failure — `gh api repos/<o>/<r>/actions/jobs/<id>/logs` with escape sequences stripped, or the job tail) and reports that measured red to `@llgenie-planner` (inbox triage) with the PR, the branch, the run/job + sha, and the log-quoted cause. The `planner decides / files an issue / delegates`; it does NOT expect this lane to fix — this lane reports based on the log. Do NOT call a red from a check name or a status colour alone: read the log first, because a cancelled run reads as `fail`, a job that can't load has 0 jobs and every rollup reads clean, and an owner-disabled producer turns a dependent's gate red (all measured). Only after reporting a measured red to the planner does this lane file/comment anything itself, and a gap that is genuinely a new issue gets one issue create (never a fan-out), citing the sha it was measured at.

**Scope is MONITOR and ROUTE, never rebase (owner instruction 2026-10-30).** This lane measures the
pipelines and their gates; it does not rebase PRs — that is the `llgenie-pr-merge-conflict` lane's job.
On a red failure do exactly three things: (1) comment the finding on the issue/PR it belongs to, with
the `file:line` / sha / run id that proves it, without expanding scope into a fix; (2) notify
`@llgenie-pr-merge-conflict` (rebase/repair) with the PR/branch and the measured head; (3) notify
`@llgenie-planner` (inbox triage) which lane owns the red. Hand a DIRTY/CONFLICTING PR to the rebase
lane as a finding, never as your own rebase. A call to rebase someone's branch, pull it onto `main`,
or cut a rebased vehicle is a directive to another lane, not initiation by this one.

See `references/runner-queue-diagnosis.md` when jobs sit in `queued` and never start (the label-vs-
capacity decision, and the one-line probe that settles it),
`references/pipeline-map.md` for the verified map of all 22 workflows (trigger, cron, consumer),
`references/verification.md` for how to prove a change fast (container probe) and for real
(`make test-unit`, streamed), including what evidence each class of fix owes the PR, and
`references/ci-job-selection.md` before changing WHICH jobs a PR runs (trigger-level filters, the
always-present scope check, and the two invariants that must stay green),
`references/auto-merge-identity.md` before touching the merge gate's tokens or an approving step (which
identity approves, which merges, and why an installation token cannot be asked who it is),
`references/agent-profiles.md` before adding a file under `agents/`, touching a checker that several PRs
already carry, or turning a fleet-wide rule into one canonical copy with owned exemptions — and for the
half of that comparison a CI runner cannot make (the counted skip, the host-side caller, and the
truncated/diverged/missing/tree-ahead classification).
`references/shared-branch-coordination.md` before pushing onto a branch another lane is already authoring —
the live-head / adapt-additively / grep-before-re-add / double-build rules for a multi-lane PR.
`templates/workflow-step-probe.py`
is a copy-and-adapt test that executes a workflow step with its commands stubbed, for pinning behaviour
instead of shell spelling (see the pitfall of that name).
