# Reactor-filed issues carry the run id, not the commit title

## ADDED Requirements

### Requirement: A filed tracker's `**run:**` field is the numeric run id and the reproduction command cites the same id

`run-failure-reactor`'s `issue_body()` MUST place the **numeric run id** of the failed run in the
`**run:**` Technical field (threaded `run_id` from `route()` → `file_issue()` → `issue_body()`, never
`displayTitle`), MUST keep the commit title the run tested in its own `**commit title:**` field, and
MUST cite the SAME id in the body's reproduction command (`gh run view {run_id} --log-failed`), so
running the body's own command verbatim reaches the failing log. The `render_body()` six-section
shape (#745) and the line-1 marker (`workflow/job@sha`, the dedupe key) MUST stay unchanged.

#### Scenario: a filed tracker's run field and reproduction command both carry the run id

Given a failed CI run with a known numeric run id and a `displayTitle`, when the reactor files the
tracker, then the `**run:**` Technical field contains that numeric id (not the `displayTitle`), the
`displayTitle` appears in its own `**commit title:**` field, and the `gh run view <id> --log-failed`
reproduction command in the same body uses that exact id.

#### Scenario: the new test asserts body-id == command-id and fails on the pre-change renderer

Given the issue-body renderer before this change, when the new negative-control test renders a body
from a run dict and a run id, then it FAILS (the `**run:**` carries `displayTitle`, not the id), and
when it runs against the change it PASSES (the body contains the run id and the id in the suggested
command equals the id in `**run:**`).
