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

Branch `feat/ci-dispatch-roster` (from main `1dcbf4c3a`): gate + 10/10 tests
green locally, unit suite + PR follow in the same change.
