# Tasks

- [x] `scripts/run_failure_reactor.py` gains a stdlib `classify_workflow(workflow) -> Lane | None`
      with `Lane` constants for the implementer, ci-pipelines, docs and engine lanes; a product
      workflow (`CI`/`pipeline`) routes to `agent:implement`, a pipeline/gate/bot workflow to
      `agent:ci-pipelines-maintainer`, an engine workflow to the engine lane (no implementation
      label, lane named), and an unclassified workflow to `None` (no implementation label).
- [x] `file_issue()` applies the classified lane's label (or none) instead of the single hardcoded
      `IMPLEMENT_LABEL`; `issue_body()` names the owning lane (`**owned by lane:**`) and the
      failure class (`**failure class:**`).
- [x] `marker(workflow, step)` — the dedupe key is class-level `WORKFLOW/STEP` (no run sha), so a
      repeated broken gate (same workflow, same failing step, different sha) files nothing.
- [x] `route()` classifies the workflow, prints the lane, builds the class-level marker with the
      failing step, and threads the lane into `file_issue`.
- [x] `tests/test_run_failure_reactor.py` pins the acceptance cases: pipeline gate → ci-pipelines
      label; product `CI` → implementer label; unclassified → no implementation label with the
      class named; engine → no implementation label with the engine lane named; repeated broken
      gate → files nothing. The gh stub's `issue create` branch no longer forces a label.
- [x] Reactor suite green: `tests/test_run_failure_reactor.py` 26/26 pass.
- [x] Docs trio: `docs/changes.d/2026-11-08-reactor-route-b-lane-2076.md` (one table row) +
      `agent-wiki/2026-11-08-reactor-route-b-lane-2076.md` narrative + regenerated `CHANGES.md`;
      `docs/BOTS.md` Route B section updated; `make check-docs` green.
- [x] Fast gates green from the agent tree: `make test-unit` (reactor + issue-body + registry-key
      suites), `make check-wiring`, `make lint`.
