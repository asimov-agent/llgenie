# workflow-guards — proposal

Issue: [#295](https://github.com/asimov-agent/llgenie/issues/295)

## Why

Every `workflow_dispatch` workflow is supposed to carry the #122 guard (only the owner, a collaborator
with write access, or the bot may start it). Audited on `main`, the rules had drifted apart:

| shape | workflows | what it accepted |
|---|---|---|
| `gh api …/collaborators/<u>/permission` for **actor + triggering_actor**, `admin|maintain|write` | issue-bot, rebase-bot, code-review-bot, publish-agent-image | the intended rule |
| `curl` on `/collaborators/<actor>` expecting `204` | ci.yml, engine-bump, engine-bump-rebase, registry-sync | **ANY** collaborator level (204 is returned for read/triage too), actor only |
| a step inside the job, `admin|write`, actor only | fix-bot | no `triggering_actor`, no `maintain` |
| **none** | **queued-alarm** | everything: it holds `issues: write` and runs `--comment` with `BUMP_TOKEN` |

And `ci.yml`'s `guard` job declared `outputs.allowed` + wrote `allowed=true|false` while **no job
consumed it** — the refusal was the step's non-zero exit all along, so a reviewer reading the file
believed a value was consulted.

## What Changes

- **One guard body, everywhere**: the `.permission` check for `github.actor` **and**
  `github.triggering_actor`, accepting exactly `admin|maintain|write`, refusing with a non-zero exit. The
  whole step — its `name:`, `env:` and the `run:` script — is byte-identical in all eleven guard sites:
  the ten `workflow_dispatch` workflows (in fix-bot the guard is a step inside its dispatch-only `fix`
  job) plus `ci.yml`, which guards the publish jobs that run on `pull_request`/`push`.
- **`queued-alarm.yml` gets the guard** (and `alarm` needs it) — it was the only dispatchable workflow
  without one.
- **`ci.yml`'s dead output is removed**, with the comment stating that the refusal is the non-zero exit
  and that every publishing job reaches the guard through `needs`.
- **`tests/test_workflow_guards.py`** (wired into `make test-unit`) holds the ten dispatchable workflows
  to: a guard exists, it is write-level for both actors, it actually gates the work (`needs` or a
  dispatch-only job), and no guard declares an output nobody reads. It scans **every** workflow for the
  last rule, because the dead-output finding was in `ci.yml`, which nobody dispatches. A sixth rule pins
  the one body itself: every guard step is byte-identical, so a fix to the rule cannot land in one
  workflow and miss the other ten.

## Not covered

- The macOS runner queue (#254) and the other bot-protocol issues (#291/#292 shipped in #298, #296 in #299).
- Branch protection / environment approvals: a GitHub-side control, not a workflow file.

Refs: #122 (the guard's origin), #107 (no self-skipping job), #276 (the dispatch form beside it).
