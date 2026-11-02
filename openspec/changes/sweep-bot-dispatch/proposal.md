# Sweep bot dispatch verifiability

## Problem

The weekly `all-pipelines` sweep (`.github/workflows/all-pipelines.yml`, issue #1102) dispatches every
dispatchable active workflow as `github-actions[bot]` via `GITHUB_TOKEN`, then awaits each run's own
verdict. Each target workflow's trigger guard (`Owner / collaborator trigger guard`, byte-identical in
every workflow) admits the repository bot ONLY when the run's head repository is this repository
(`HEAD_REPO == REPO`). On a `workflow_dispatch` the head repository is empty (`github.event.pull_request`
is null), so the guard's only bot carve-out can never fire; the bot is not a collaborator (permission
read answers `none`), and the six active targets — arms, ci-requeue, engine-build, engine-bump, holds,
publish-agent-image — refuse the sweep's own dispatch by design.

Measured on the 2026-11-02 00:43 sweep (run 41368662505): the sweep table shows all six as
`completed/failure` because each refused `github-actions[bot]` before any secret was read — arms
41368685898, ci-requeue 41369636784, engine-build 41369920066, engine-bump 41374213796, holds
41374530076, publish-agent-image 41374811640 — each guard log: `Refused: github-actions[bot] is not
the owner or a collaborator with write access (permission: none)`.

## Why it matters

The sweep's contract is "dispatch every dispatchable pipeline, await its verdict, fail iff any
non-disabled run failed". With the six, the verdict is refused before any pipeline runs — the sweep can
NEVER verify them through its own dispatch path, and the sweep itself reds by design every run. #1474
(all-pipelines verify) closed as verified, but that verification was via an owner/collaborator dispatch,
not the sweep's own bot path; the sweep path is unverifiable by design today.

## How we fix it

1. Guard carve-out: extend the repository-bot allowance so the bot also passes when the run is a
   `workflow_dispatch` of this repository — `github.event_name == workflow_dispatch`. A
   `workflow_dispatch` can only be started by a token with write access to THIS repository and can only
   target THIS repository's own refs (a fork cannot dispatch our workflows, cannot add refs here), so
   the event itself carries the same-repo-head guarantee that `HEAD_REPO` provides on a PR event —
   reached via event instead of the (empty) head repo.
2. Dispatch-at-own-ref: the all-pipelines sweep dispatches each target at the ref it is running from
   (`github.ref_name`) instead of a hardcoded `main`, so a PR-head sweep verifies the PR-branch
   workflows (whose guards carry the carve-out) and the weekly-on-main sweep verifies main — the
   umbrella sweeps the tree it is running, and a pre-merge green sweep becomes provable.
3. Sweep honesty: when a dispatched run nevertheless fails at its own trigger guard (a workflow that
   still carves no bot path), the sweep's table names that workflow as `NOT VERIFIED — refused at its
   own trigger guard` instead of a bare `completed/failure`, so an unverifiable pipeline is never
   disguised as a verdict.
4. Negative control preserved: the carve-out is scoped to the `workflow_dispatch` EVENT. A bot acting
   as the actor of a foreign PR head (`HEAD_REPO != REPO`), or on a non-dispatch event with no head,
   is still refused. The #495/#510 guarantee is not weakened.

## Benefit

The weekly sweep becomes a truthful gate: green once every dispatched run concludes, and the six become
verifiable through the sweep's own dispatch (the guard no longer refuses the repo's own automation).
A workflow that still cannot be verified is named, with the reason, instead of masquerading as
`completed/failure`. The foreign-head refusal (#495/#510) is unchanged.

## Acceptance criteria

- [ ] `gh workflow run all-pipelines.yml` at current origin/main ends green when every dispatched run
      concludes (guard carve-out works for the bot dispatch path)
- [ ] the sweep's table names every workflow it could not verify, with the reason, instead of a bare
      `completed/failure`
- [ ] a negative control: a bot-dispatch of one of the six still refuses a foreign-head actor (the
      #495/#510 guarantee is not weakened)

## Not covered

- Re-enabling the 14 `disabled_manually` workflows (owner's call).
- Re-verifying #1474-#1504 (already closed).
- Changing the guard's owner/collaborator allowance.

## Technical

- `.github/workflows/*.yml` — every guard site (`name: Owner / collaborator trigger guard`) gains
  `EVENT: ${{ github.event_name }}` and `REF: ${{ github.ref }}` in its env and a
  `[ "${EVENT:-}" = "workflow_dispatch" ]` carve-out in its run script; all sites stay byte-identical
  (guarded by `tests/test_workflow_guards.py::test_every_guard_step_is_byte_identical`).
- `.github/workflows/all-pipelines.yml` — the sweep step passes `REF="${{ github.ref_name }}"` so it
  dispatches targets at the ref it runs from.
- `scripts/all_pipelines.py` + `tests/test_all_pipelines.py` — when a dispatched run concludes
  `failure`, query `/actions/runs/{id}/jobs`; a failed `guard` job with the rest skipped means a
  guard-refusal — render `NOT VERIFIED — refused at its own trigger guard` (no bare
  `completed/failure`).
- `tests/test_workflow_guards.py` — new execution tests: bot + `workflow_dispatch` (any of the repo's
  own refs) -> allowed; bot + non-dispatch event (no head) -> refused; bot + same-repo PR head ->
  allowed; bot + foreign PR head -> refused (existing).
- `docs/SECURITY.md` / `docs/BOTS.md` — the guard carve-out line updated to describe the
  `workflow_dispatch` bot path and the sweep's dispatch-at-own-ref behavior.
