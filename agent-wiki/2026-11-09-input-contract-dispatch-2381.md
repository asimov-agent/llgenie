# Input-contract workflow_dispatch for review-verdict and engine-build-pr-trigger (issue #2381, PR #2382)

## What changed

The #1505 "7 workflows missing workflow_dispatch" roster count mixed a real gap with
by-design (5 of 7 are intentionally non-dispatchable). The two remaining event-driven
workflows got a real input-contract `workflow_dispatch`, not a bare one-liner that would
have made them 0-job (the zero-job-pending class, #295).

- `review-verdict.yml`: `on: workflow_dispatch` with REQUIRED `pr_number` + `head_sha`. A
  dispatch resolves the PR and its head via the API, **asserts `head_sha` == the PR's
  current head** (a stale name exits and records nothing — a finding, not a pass), maps
  the PR's latest approved-or-changes decision and records the `make bot-verdict` marker
  with >=1 job completing. A dispatch-only byte-identical `/collaborators/` actor guard
  (owner/collaborator-with-write, #295/#1571) gates it; the `pull_request_review` path
  keeps its same-repo head-repo guard and event-derived head/verdict/run.
- `engine-build-pr-trigger.yml`: `on: workflow_dispatch` with REQUIRED `base_ref` +
  `branch`. A dispatch resolves both refs (fetches them, stands on the head's params
  tree), runs `make engine-build-pr-trigger` over the base->head diff and awaits each
  `engine-build push=true` run's verdict; a dispatch-only byte-identical `actor-guard`
  job that `trigger` needs gates it. The `pull_request` path keeps its same-repo HEAD_REPO
  guard and exact make call. Concurrency stays the original per-PR-head group.

## Why it matters

A missed review verdict or a trigger run that died mid-wait is currently unrecoverable by
hand: `review-verdict` had no dispatch path (its only job reds/0-jobs on a non-review
event) and `engine-build-pr-trigger` had no dispatch path that could scope a base/head
pair. Both dispatches refuse anyone who is not a write-scoped collaborator, are gated
against a stale head, and the `docs/BOTS.md` dispatch table stays the source of truth
(regenerated, 30 dispatchable rows).

## Verified

`make check-dispatch-forms` green (name/header rules, required inputs, Flow targets
real); `scripts/check_workflows.py` green; `tests/test_workflow_guards.py` (16) +
`tests/test_dispatch_forms.py` (30) + `tests/test_engine_build_pr_trigger.py` (updated:
trigger surface is now `{pull_request, workflow_dispatch}` with required inputs) all pass
at the branch head. Nothing merged, nothing armed.
