# Every bot states the work it will do, before you dispatch it (issue #276)

## Why

The dispatch dialog is the interface a collaborator actually meets, and it was empty. Measured on
`main`:

- `engine-bump-rebase.yml` and `registry-sync.yml` declared a bare `workflow_dispatch:` — a naked
  *Run* button. Nothing said that the first rebases every open engine-bump PR, or that the second
  also opens issues for NEW unskilled engines.
- Every other bot had inputs, but the `name:` repeated the file name (`issue-bot`, `registry-sync`,
  `PR fix-bot`), so the Actions list was a list of filenames rather than a list of jobs.
- `fix-bot.yml` was the only file whose dispatch form explained itself.
- Nothing checked any of it, so the contract lived in a header comment, a Makefile and someone's head.

A bot you cannot dispatch without reading its YAML is a bot only its author can operate.

## What changes

- **`scripts/check_dispatch_forms.py`** — the guard (`check` / `report`), wired into `ci-unit` next to
  `check-wiring`. It fails on: a `name:` that repeats the file stem or does not describe the work; a
  bare `workflow_dispatch:` without a documented reason; an input with no `description:`, or with
  neither `default:` nor `required: true`; a missing `Trigger surface` / `Flow` / `Never` header key;
  and a README table that no longer matches the workflows.
- **Every dispatchable workflow** states the work: the `name:` says what the run does and its bound,
  every input is documented, the header block names the make target behind each stage and the
  invariants (`Never`).
- **`engine-bump-rebase` gained a `dry` input that reaches the code**: the workflow now calls a new
  `make engine-bump-rebase` target (`DRY=1` → the script's `--dry`) instead of invoking
  `scripts/engine_bump_rebase.py` inline. That is also the step-level make-target rule (one make path
  per stage), and it is the same class of defect as #270.
- **`queued-alarm.yml`** now calls `make queued-alarm` instead of `python3 scripts/queued_run_alarm.py`
  inline — the fix for #270, which this PR closes.
- **The README's dispatch table is generated and verified** (`make dispatch-forms-report` prints it;
  `make check-dispatch-forms` fails when it is stale), so the page a dispatcher reads cannot drift
  from the pipelines it describes.

## What does NOT change

No behaviour change to any bot: the same make target runs the same work, nothing new merges anything,
and `ci.yml` / `pipeline.yml` / `published.yml` (CI, not bots) are untouched.
