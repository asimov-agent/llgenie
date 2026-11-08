# run-failure reactor routes a filed issue to the lane that owns the fix (issue #2076)

## What was verified

- `scripts/run_failure_reactor.py::classify_workflow(workflow)` maps a failing workflow's display
  `name:` to a `Lane`. A product workflow (`CI` / `pipeline`, which run the product's own gates)
  routes to the implementer (`agent:implement` — the existing behaviour, preserved for its actual
  case). A pipeline/gate/bot/script workflow (`ci-verdict`, `ci-requeue`, `rebase-bot`,
  `main-ruleset`, `arms`, `*`-bot, …) routes to `agent:ci-pipelines-maintainer` (the ci-pipelines
  lane). An engine workflow (`engine-bump`, `engine-build`, …) routes to `llgenie-engine-improver`,
  which has no `agent:*` queue label on the repo, so its issue is filed with NO implementation
  label and the lane named in the body. A workflow that cannot be classified confidently returns
  `None` — the issue is filed with NO implementation label and the failure class named in the body,
  never defaulted to the product implementer.
- `file_issue()` now passes the classified lane's label (or none) to `issue create` instead of the
  single hardcoded `IMPLEMENT_LABEL`; `issue_body()` carries `**owned by lane:**` and
  `**failure class:**`.
- `marker(workflow, step)` — the dedupe key is class-level `WORKFLOW/STEP` (the failing step, not
  the run sha), so N runs of one broken gate (different shas, same step) collapse into ONE issue.
  Measured before (2026-11-08 at `origin/main@e51f2fd0`): `#2056`/`#2067`/`#2070` were three
  near-identical `ci-verdict` issues, `#2055` a `ci-requeue`, all labelled for the product
  implementer.
- Reactor suite green: `tests/test_run_failure_reactor.py` (26 tests) + `tests/test_issue_body.py`
  + `tests/test_registry_keys.py` + `tests/test_workflows_valid.py` pass. Fast gates run from the
  agent tree.

## Key decisions

- **Lane, not label:** the classification returns a `Lane` (name + label), so the issue body names
  the owning lane even when that lane has no queue label (engine) or the workflow is unclassified.
- **Never default to the implementer:** an unrecognised workflow is filed unlabelled with the
  failure class named, per the issue's acceptance — an unclassified failure is not proof of a
  product defect.
- **Class-level dedupe:** the step name, not the run sha, is the marker key, so three runs of one
  broken gate become one issue. The `filed_phrase` quote-strip (issue #1990) is unchanged.
- The reactor still dispatches `fix-bot` (Route A) when a pushable PR exists — that path is
  untouched (issue #2076 explicitly scopes this to the Route-B label).

## Status

Implementation complete, suite + fast gates green; OpenSpec change
`openspec/changes/reactor-route-b-lane-label/` (proposal.md + specs/run-failure-reactor/spec.md +
tasks.md). Closes #2076.
