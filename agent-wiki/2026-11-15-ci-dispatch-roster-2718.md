# CI dispatch roster (issue #2718)

## What was verified against the spec

- The AGENTS.md CI-discipline bullet was rewritten from the blanket ban
  ("The agent never manually starts a CI pipeline. No `gh run rerun`, no
  `gh workflow run` / `workflow_dispatch`") to the owner's actual permission
  model: a CI pipeline starts from a GitHub event, **or from a dispatch a
  permitted principal starts — the owner, a collaborator, and GitHub itself
  (the Actions bot)**. The automated agent still never dispatches and never
  pumps the queue: no `gh run rerun`, no requeue or re-trigger loops; a wedge
  is fixed by pushing a commit. The retired ci-requeue healer (#2702, retired
  by branch `feat/2702-ci-requeue-retirement` / PR #2717) stays named as the
  forbidden shape.
- `scripts/check_ci_discipline.py::AGENTS_PIN_PHRASES` now pins
  `("owner, a collaborator, and GitHub itself", "gh run rerun", "tests only",
  "agent-image", "weekly")`. The blanket-ban phrase is no longer required.
- New test `test_the_dispatch_roster_is_pinned_and_the_blanket_ban_is_not`
  proves both directions: the real AGENTS.md names the roster and keeps the
  rerun ban; replacing the roster with the old blanket-ban sentence reddens
  `make check-ci-discipline`.
- OpenSpec: change `ci-dispatch-roster` carries a MODIFIED requirement on the
  `ci-discipline` capability; `make openspec-validate NAME=ci-dispatch-roster`
  exits 0.

## Key decisions

- The fix rides as its own issue/PR (#2718) because PR #2704 (the original
  discipline gate) is already merged; the OpenSpec delta form keeps the
  `ci-discipline` spec the referee instead of editing merged history.
- No workflow file changes: the guard jobs already enforce the owner/
  collaborator/bot roster at trigger time; only the rules wording and its
  pin phrases described it wrongly.

## Current status

Branch `feat/ci-dispatch-roster` (from main `1dcbf4c3a`): gate + 11/11 tests
green locally, unit suite + PR follow in the same change.

## Follow-up landed in the same change (issue #2721)

The owner restated the mode explicitly: the agent verifies with `make` targets
on its own tree (locally, on the host) and is never the one starting a GitHub
CI pipeline; pipelines are started by humans (owner/collaborator), scheduled
(cron) lanes, and GitHub itself reacting to events (push, PR creation, PR
merge, `workflow_run`, label) — and the one exception is dispatching to test a
workflow that is failing (debugging the pipeline itself). The bullet now states
this; `AGENTS_PIN_PHRASES` gained `"verifies locally with `make`"` and
`"test a workflow that is failing"`; the new test
`test_the_local_make_mode_and_the_failing_workflow_exception_are_pinned`
proves both directions (erasing the mode sentence is a finding naming
AGENTS.md). OpenSpec delta extended with the matching scenario.
