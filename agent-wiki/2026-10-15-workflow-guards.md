# One trigger guard for every dispatchable workflow (#295)

## Why

Each `workflow_dispatch` workflow is supposed to refuse anyone who is not the owner or a write-level
collaborator (#122). The audit found four shapes:

| shape | workflows | accepted |
|---|---|---|
| `.permission` for actor + `triggering_actor`, `admin\|maintain\|write` | issue-bot, rebase-bot, code-review-bot, publish-agent-image | the intended rule |
| `curl` `/collaborators/<actor>` == `204` | ci.yml, engine-bump, engine-bump-rebase, registry-sync | **any** collaborator level (204 also for read/triage), actor only |
| step-level, `admin\|write`, actor only | fix-bot | no `triggering_actor`, no `maintain` |
| **none** | **queued-alarm** | everything — it holds `issues: write` and comments with `BUMP_TOKEN` |

`ci.yml`'s guard also declared `outputs.allowed` and wrote `allowed=true|false` while no job read it: the
refusal was the step's non-zero exit, so the output only made a reviewer believe a value was consulted.

## What landed

- One guard body — `.permission` for **both** actors, `admin|maintain|write`, refusal as a non-zero exit —
  is now byte-identical (name, `env:` and `run:`) across all eleven guard sites: the ten dispatchable
  workflows, plus `ci.yml`, which guards the publish jobs that run on `pull_request`/`push`.
- `queued-alarm.yml` got the guard job (`alarm` needs it) — it was the only dispatchable workflow without
  one; its header now says so, and that `needs:` is a gate rather than the `if:` #107 forbids.
- `ci.yml`'s dead output is gone, with the comment stating the mechanism.
- `tests/test_workflow_guards.py` (in `make test-unit`) holds every dispatchable workflow to: guard
  present, write-level, both actors, actually gating, and no dead guard output — that last rule over
  **every** workflow, since the finding was in the one workflow nobody dispatches — and one more rule pins
  the body itself: every guard step is byte-identical (`test_every_guard_step_is_byte_identical`).
- The first PR run was red only on the two tests that pinned the removed `curl` + `Authorization` guard
  (`test_engine_bump_rebase.py::test_guard_sends_the_default_token_variable`,
  `test_engine_bump.py::test_guard_keeps_default_token`); both now assert the `gh api` + default-token
  shape — the guard hands the CLI the run's own `github.token`, and no workflow hand-builds a header.

## Verification

- `tests/test_workflow_guards.py`: **6 passed** in `llgenie/test:latest`; against the pre-fix workflows
  (`git show origin/main:…`) the same file gives **5 failed, 1 passed** (missing guard, weak guard,
  ungated guard, dead output, drifted body), and a deliberately drifted guard body fails the byte-identity
  case on its own.
- `make lint`, `make check-docs`, `make check-wiring`, `make check-dispatch-forms`, `make
  openspec-validate NAME=workflow-guards`.

## Note

GitHub already refuses `workflow_dispatch` from a user without write access, so no outsider could start
these upstream. The guard is the second line — it covers the non-dispatch paths (`issues: [labeled]`, a
fork-side run, a re-run by another actor) and keeps the rule visible in the file.
