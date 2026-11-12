# Tasks — workflow-actor-guard-scan (#2526)

- [x] 1. `scripts/check_workflows.py`: add the helpers the new rules need — a `run:`-block
      carve-out reader (column-zero-aware: a `run: |`/`run: >` line and its deeper-indented body
      are excluded from expression scans) on top of the existing `_on_triggers` and
      `workflow_run` roster parsing.
- [x] 2. R1 in `scripts/check_workflows.py`: top-level `permissions:` required per file
      (finding `workflow-permissions/<file>`), `permissions: write-all` refused
      (finding `workflow-write-all/<file>`).
- [x] 3. R2 in `scripts/check_workflows.py`: `pull_request_target` trigger refused
      (finding `workflow-forbidden-trigger/<file>/<trigger>`).
- [x] 4. R3 in `scripts/check_workflows.py`: open-trigger set
      (`pull_request`, `workflow_run`, `issues`, `issue_comment`, `pull_request_review`,
      `pull_request_review_comment`, `label`, `discussion`) requires the
      `github.triggering_actor` signature outside `run:` blocks (finding
      `workflow-actor-guard/<file>`), OR transitive derivation through a `workflow_run` roster
      whose every named workflow passes (a) or is internal-only; internal triggers
      (`push`, `schedule`, `workflow_dispatch`, `workflow_call`) exempt. Real fleet must pass
      with zero exemptions: `auto-merge.yml` and `zero-job-pending.yml` by derivation,
      `registry-liveness.yml` and `pipeline.yml` as internal.
- [x] 5. `.github/workflows/ci.yml` and `.github/workflows/pipeline.yml` gain explicit top-level
      `permissions:` blocks whose scope preserves what their jobs rely on today (measure each
      job's writes with `GH_TOKEN`; jobs keep their existing job-level elevations; PR CI itself —
      which RUNS `ci.yml` — is the behavioral proof).
- [x] 6. `tests/test_workflow_actor_gates.py`: synthetic fixture trees for every rule
      (missing permissions, write-all, pull_request_target, open trigger without guard,
      guard-only-inside-run, guarded roster clean, unguarded roster taints follower,
      internal-only exempt) + a real-tree assertion that `findings(REPO_ROOT)` carries none of
      the new finding keys after the fixes land. `pytest tests/test_workflow_actor_gates.py`
      rc=0.
- [ ] 7. `make check-workflows` and `make workflows-report` (report line stating per-file
      trigger class + guard state) rc=0; gate already wired into `ci.yml` guard job, `scope.yml`,
      and `lane-preflight` — no new wiring; `make lane-preflight` rc=0.
- [ ] 8. `docs/BOTS.md` three-party paragraph names the new rules (`make check-docs` rc=0). The
      `AGENTS.md` §"Every workflow file is validated before it can merge" bullet is the
      approval-blocked half (protected-file prompts timed out twice 2026-11-12): filed as linked
      **#2527** and recorded in the issue's `Not covered`. Agent-wiki entry naming #2526 + the PR.
- [ ] 9. `make openspec-validate NAME=workflow-actor-guard-scan` rc=0; commit `closes #2526`,
      push `feat/workflow-actor-guard-scan`, PR body mirrors the issue with ticked AC +
      `closes #2526`; PR CI green and `mergeStateStatus` CLEAN (auto-merge lands it).
