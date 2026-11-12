# Workflow actor guard scan (issue #2526)

## Why

The three-party rule — only the **owner**, a **collaborator**, or the **GitHub bot** may drive a
workflow — is documented (`docs/BOTS.md`, "Only collaborators, the `github-actions[bot]`, and the
owner may trigger the workflows") and implemented as an inline trigger guard (`ACTOR: github.actor`
+ `TRIGGER: github.triggering_actor` + collaborator-API check), but **no gate checks that it is
there**. Measured at `main` tip `d8700c60e`: the guard signature is present in 32 of 36 workflow
files; four carry none (`auto-merge.yml` — the one that merges with the owner PAT,
`zero-job-pending.yml`, `registry-liveness.yml`, `pipeline.yml`), and two files (`ci.yml`,
`pipeline.yml`) declare no top-level `permissions:` block, so their token scope falls back to the
org-wide default instead of a stated minimum. A new or edited workflow can today expose privileged
automation to a non-collaborator-reachable event and stay green.

## What Changes

Extend the existing `make check-workflows` gate (`scripts/check_workflows.py` — already runs in
`ci.yml`'s required `guard` job, in `scope.yml`, and in `make lane-preflight`) with three
git-local, deterministic rules over **every** `.yml` in `.github/workflows/`:

- **R1 explicit token scope:** every workflow declares a top-level `permissions:` block;
  `permissions: write-all` is refused. `ci.yml` and `pipeline.yml` gain top-level blocks that
  **preserve the effective scope their jobs rely on today** (measured from their jobs' uses — no
  behavior change), and their jobs keep their existing job-level elevations.
- **R2 forbidden trigger:** `pull_request_target` is refused outright (zero uses today; standing wall).
- **R3 the three-party rule per file**, over the fleet's whole START surface — pipelines that start
  automatically when a PR is created and pipelines that start manually (owner clarification
  2026-11-12): a workflow whose trigger surface includes an outsider-reachable event
  (`pull_request`, `workflow_run`, `issues`, `issue_comment`, `pull_request_review`,
  `pull_request_review_comment`, `label`, `discussion`) must either
  - (a) carry the guard signature — a reference to `github.triggering_actor` **outside any `run:`
    block** (in `if:` or step `env:`, the same expression discipline the file already enforces) —
    which for a PR-triggered run IS a check of who created the PR, or
  - (b) be **transitively guarded**: its only outsider-reachable trigger is `workflow_run` and every
    workflow named in its `workflows:` roster is itself guarded or internal-only. This is GitHub's own
    event model made checkable, and it is the reasoning `zero-job-pending.yml`'s header already states (#1410).
  Internal triggers (`push`, `schedule`, `workflow_dispatch`, `workflow_call`) need no guard: GitHub
  grants all four only to write-capable accounts, repo-owned clocks, or repo-local callers. After the
  change all 36 files satisfy the rule with **no exemptions**: `auto-merge.yml` (roster CI + ci-scope,
  guarded) and `zero-job-pending.yml` (roster ci-requeue, guarded) pass by derivation;
  `registry-liveness.yml` (push+schedule) and `pipeline.yml` (workflow_call) pass as internal.

No new Makefile target and no new CI wiring: the rules land inside an existing fast gate.

## Impact

- Affected specs: `workflow-actor-guard` (new capability)
- Affected code: `scripts/check_workflows.py` (new rules + report line), `.github/workflows/ci.yml`
  and `.github/workflows/pipeline.yml` (top-level `permissions:` blocks), new test module
  `tests/test_workflow_actor_gates.py`, docs: `docs/BOTS.md` three-party paragraph names the gate;
  the `AGENTS.md` workflow-validation-section bullet is approval-blocked (protected file) and filed
  as the linked follow-up #2527.
