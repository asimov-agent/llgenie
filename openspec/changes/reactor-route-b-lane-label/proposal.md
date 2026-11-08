# route the run-failure reactor's filed issue to the lane that owns it

## Why

`run_failure_reactor.py` files a Route-B issue (a failed run with no pushable PR) labelled always
`agent:implement` (`IMPLEMENT_LABEL = "agent:implement"`, applied at the single `issue create`
`--label`). That label is the queue the PRODUCT implementer (`llgenie-issse-implementer`) drains.
A failure of a CI **pipeline** (a gate, a bot, a workflow file — `ci-verdict`, `ci-requeue`,
`rebase-bot`, `main-ruleset`, …) is not product code: its fix lives in `.github/workflows/**` and
`scripts/*_verdict.py`, owned by the `llgenie-ci-pipelines-maintainer` lane. Measured 2026-11-08 at
`origin/main@e51f2fd0`, every open reactor-filed issue carries the same label regardless of domain:
`#2056`/`#2067`/`#2070` (`ci-verdict` ×3) and `#2055` (`ci-requeue`) are all pipeline failures
routed to the product implementer.

Two consequences:
1. **Wrong owner.** A pipeline failure queues behind product-code work and is picked up by a lane whose
   remit excludes the file the fix lives in.
2. **Duplicates accumulate.** Three near-identical `ci-verdict` issues exist because the dedupe marker
   is `workflow/job@SHORTSHA` — run-scoped, so three runs of one broken gate file three issues.

## What Changes

- **`scripts/run_failure_reactor.py::classify_workflow(workflow)`** — a stdlib classifier that maps the
  failing workflow's display `name:` to the lane that owns the fix, with `Lane` constants for each
  lane. A product workflow (`CI` / `pipeline`, which run the product's own gates) routes to the
  implementer (`agent:implement`, unchanged); a pipeline/gate/bot/script workflow routes to the
  ci-pipelines lane (`agent:ci-pipelines-maintainer`); an engine workflow routes to the engine lane
  (which has no `agent:*` queue label — filed with no implementation label, the lane named in the
  body); a workflow that cannot be classified confidently routes to **None** — filed with NO
  implementation label and the class named in the body, never defaulted to the implementer.
- **`file_issue()`** applies the classified lane's label instead of the single hardcoded
  `IMPLEMENT_LABEL`; `issue_body()` names the owning lane and the failure class.
- **`marker(workflow, step)`** — the dedupe key becomes class-level `WORKFLOW/STEP` (the failing
  step, not the run sha), so N runs of one broken gate collapse into one issue.
- **`tests/test_run_failure_reactor.py`** — the gh stub's `issue create` branch no longer forces a
  label; new tests pin the acceptance cases (`ci-verdict` → ci-pipelines label, product workflow →
  implementer label, unclassified → no implementation label, repeated broken gate → files nothing).

## After

A failed pipeline reaches the lane that can actually fix it on the first filing. The board stops
showing pipeline reds parked behind product-code work, and same-class failures stop multiplying into
one issue per run. A product failure routes exactly as it always has.
