# all-pipelines joins the architecture bot roster (issue #3098)

## Change

`docs/ARCHITECTURE.md`'s `## Bots` table now carries a row for
`.github/workflows/all-pipelines.yml`. The reference tree at
`bc01c17afab449f3bcc5a9412d88d8a19f6a37c8` had 36 workflow files but only 18 rows in
that table; `all-pipelines.yml` was the only scheduled workflow with no row. The old doc
mentioned the sweep only parenthetically in the `run-failure-reactor.yml` row, and
`docs/BOTS.md` named `make all-pipelines-sweep` without the workflow file or its cron.

## Measured workflow facts

- `on.schedule.cron = "27 4 * * 6"` — weekly Saturday 04:27 UTC, its own odd minute
  (issue #275) — plus a bare `workflow_dispatch` with no inputs (`# dispatch: no inputs`).
- `permissions.actions = write`; one static `all-pipelines-sweep` concurrency group with
  `cancel-in-progress: false`; owner/collaborator guard before any secret is read.
- `make all-pipelines-sweep` (`scripts/all_pipelines.py`) enumerates the checked-out
  tree's workflows, classifies active/disabled/self via the API, dispatches and awaits
  every dispatchable non-self run's OWN verdict (#964), prints
  `workflow · dispatched run id · status/conclusion · completed_at` plus
  `N ok · M failed · K disabled`, names every disabled workflow, and fails at the end
  iff any non-disabled run failed (issue #1102).

## Why this is a docs-only fix

The workflow already behaves as documented in its own header and `docs/BOTS.md`;
nothing in the tree was wrong. The architecture roster was simply smaller than the
scheduled surface, so an architecture audit could not enumerate every weekly pipeline
from that table. No gate, workflow, or script was changed.

## Verification

- `make -s check-docs` rc=0 (`CHANGES.md` regenerated from the note trio).
- `PATH=$HOME/llama-gguf-tools/.venv/bin:$PATH make -s check-ci-discipline` rc=0.
- `make -s check-workflows` rc=0, `make -s check-dispatch-forms` rc=0, `make -s lint` rc=0.
- Cron comparison of all 18 `## Bots` rows against their workflow `on.schedule` blocks:
  zero mismatches after the new row.
