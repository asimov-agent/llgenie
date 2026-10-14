# Every dispatchable workflow now states the work it will do (#276)

## Why

The dispatch dialog is the interface a collaborator actually meets, and it was empty. Measured on
`main` before this change — `python3 scripts/check_dispatch_forms.py check` reported 19 violations:

| what the guard found | example |
|---|---|
| a `name:` that repeats the file name | `name: registry-sync`, `name: issue-bot`, `name: engine-bump`, `name: engine-bump-rebase` |
| a `name:` with no description at all | `name: PR fix-bot`, `name: Queued-run alarm`, `name: Publish agent image` |
| a **bare `workflow_dispatch:`** | `engine-bump-rebase.yml`, `registry-sync.yml` — a naked *Run* button, nothing said what the run does |
| an input with undefined empty-meaning | `fix-bot.yml`'s `pr_number` and `branch` had `description` but no `default` and no `required` |
| no header block | 6 of 7 files had no `Trigger surface` / `Flow` / `Never` |
| no README table | the dispatch surface was documented nowhere in one place |

## What changed

- **`scripts/check_dispatch_forms.py`** — `check` (gates `ci-unit`) and `report` (generates the table).
  It fails on: a name that repeats the stem / has no `— what it does` / describes the work in under 10
  characters; a bare dispatch form without `# dispatch: no inputs — <reason>`; an input with no usable
  `description:` or with neither `default:` nor `required: true`; a missing header key; a stale README
  table.
- **All seven dispatchable workflows** now name the work, document every input, and carry the header
  block. The names read as jobs in the Actions list:
  `issue-bot — implements ONE issue per run as a reviewable PR (never merges)`,
  `fix-bot — repairs a failing PR branch until its checks pass (never merges)`,
  `engine-bump-rebase — rebases every open engine-bump PR onto the latest main`, …
- **`engine-bump-rebase`'s `dry` input is real**: the workflow now calls the new
  `make engine-bump-rebase` target (`DRY=1` → the script's `--dry`) instead of invoking
  `scripts/engine_bump_rebase.py` inline. A form that offers an input nothing reads is worse than no
  form, because the form then lies. This also puts the step back on the one-make-path-per-stage rule.
- **`queued-alarm.yml`** calls `make queued-alarm` instead of `python3 scripts/queued_run_alarm.py`
  inline — the fix for #270, which this PR closes.
- **The README table is generated and verified**: `make dispatch-forms-report` prints it,
  `make check-dispatch-forms` fails when it drifts from the workflows, so the page a dispatcher reads
  cannot describe a pipeline that no longer exists.

## Testing

`tests/test_dispatch_forms.py` — 22 tests, wired into `test-unit`. Every rule is broken on a fixture
workflow (`name: a-bot` in `a-bot.yml`; `name: PR fix-bot`; a bare `workflow_dispatch:`; the exemption
with a one-word reason; an input with no description; an input with neither default nor required; a
missing `# Never:`), and one test asserts the exit code CI gates on. Then the guard is run over this
repository, because a convention the repo itself violates is not a convention:

```
$ uv run ... pytest tests/test_dispatch_forms.py            # 22 passed
$ make check-dispatch-forms
[check-dispatch-forms] OK 7 dispatchable workflow(s) state the work they do, their inputs are
documented, and the README table matches: engine-bump-rebase.yml, engine-bump.yml, fix-bot.yml,
issue-bot.yml, publish-agent-image.yml, queued-alarm.yml, registry-sync.yml
$ make check-wiring && make lint                            # OK
$ make -n engine-bump-rebase DRY=1
python3 scripts/engine_bump_rebase.py --dry
```

`tests/test_engine_bump_rebase.py::TestWorkflowYaml` was **updated, not duplicated**: it used to assert
`"engine_bump_rebase.py" in text`, which would have kept passing while the step bypassed make; it now
asserts the step calls `make engine-bump-rebase`, that the run block does *not* call the script
directly, that the make target runs the entrypoint, and that `inputs.dry` reaches it.

## Note on the guard's home

The reviewer bot (#269/#274) also wants a `dispatch-form` check — the two are the same rule, so when
#274 lands the bot's check should call this script rather than grow a second implementation
(`scripts/check_dispatch_forms.py` is importable and exposes `analyse` / `violations` / `table`).
