# workflow-actor-guard-scan: every workflow classified by start surface and proven three-party-only (#2526)

Date: 2026-11-12. OpenSpec change: `workflow-actor-guard-scan`. Issue: #2526.

## What was verified

- The defect, measured on `main` at `d8700c60e`: the owner/collaborator/bot trigger guard existed
  inline in 32 of 36 workflow files and nothing checked the other four (`auto-merge.yml` — merges
  with the owner PAT, `zero-job-pending.yml`, `registry-liveness.yml`, `pipeline.yml`); top-level
  `permissions:` was absent in `ci.yml` and `pipeline.yml`, which silently inherited whatever the
  org-wide token default was.
- `scripts/check_workflows.py` gained three rules over ALL `.github/workflows/*.yml` files, each
  file classified by its START SURFACE — the chain that starts on PR creation (the `pull_request`
  files and every `workflow_run` follower), the merge to main (`push`), a cron (`schedule`), or a
  manual owner/collaborator start (`workflow_dispatch`):
  - R1: explicit top-level `permissions:` required; `permissions: write-all` refused.
  - R2: `pull_request_target` refused outright (fleet uses: 0 — a standing wall).
  - R3: every outsider-reachable trigger (`pull_request`, `workflow_run`, `issues`,
    `issue_comment`, `pull_request_review`, `pull_request_review_comment`, `label`,
    `discussion`) requires the `github.actor`+`github.triggering_actor` guard signature read
    OUTSIDE `run:` script text (`_outside_run_lines()` carves `run: |`/`run: >` bodies out of the
    scan; the `RUN_LINE` regex must match the `- run:` step-list form or script text masquerades
    as gate text) — or a TRANSITIVE derivation: the file's only open trigger is `workflow_run`
    and every workflow named in its roster is itself guarded or internal (`_guard_info()`
    fixed-point loop; a roster cycle never reaches the fixed point — circular trust is no trust).
- Fleet result with ZERO exemptions: 32 signature, 2 derived (`auto-merge.yml`,
  `zero-job-pending.yml`), 2 internal (`pipeline.yml` `workflow_call`, `registry-liveness.yml`
  push+schedule). `make workflows-report` now prints a 36-line start-surface table
  (`starts-on[...] guard[signature|derived|internal|UNGUARDED]`).
- `ci.yml` and `pipeline.yml` gained top-level `permissions: contents: read`; every job keeps its
  existing job-level elevation (GitHub merges top-level with job-level; job-level wins), so no
  job's effective scope changed.

## Key decisions

- The scan CLASSIFIES internal triggers rather than exempting them: `push`, `schedule`,
  `workflow_dispatch`, `workflow_call` are three-party-only at the platform level (write-capable
  accounts, repo-owned clock, repo-local callers) — the classification is the answer to
  "who can start this", printed for every file.
- `pull_request_target` sits in BOTH R2 (outright ban) and `OPEN_TRIGGERS` (defense-in-depth).
- The AGENTS.md half of the documentation task is approval-blocked (protected-file prompts timed
  out twice) and is filed as linked follow-up **#2527**, recorded in #2526's `Not covered`.
- Gate reuses existing wiring: `make check-workflows` already runs in `ci.yml`'s `guard` job,
  `scope.yml`, and `lane-preflight` — zero new wiring (check-wiring rc=0).

## Current status

Implementation, tests (71 green across `tests/test_workflow_actor_gates.py`,
`tests/test_workflows_valid.py`, `tests/test_workflow_guards.py`), fleet gate, docs/BOTS.md
paragraph, issue/PR/commit AC mirroring all landed on `feat/workflow-actor-guard-scan`; the PR
number is named in the note's follow-up commit once the PR is open. CI-side proofs (AC4/AC5:
PR CI green, `mergeStateStatus` CLEAN) tick at the board re-poll; auto-merge lands the PR.
