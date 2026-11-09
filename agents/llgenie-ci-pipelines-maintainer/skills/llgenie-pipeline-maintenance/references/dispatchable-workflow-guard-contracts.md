# Making a newly-dispatchable workflow satisfy the guard contracts (#1886/#1887)

When a PR adds `workflow_dispatch` to a workflow that previously had no manual trigger, the
file becomes DISPATCHABLE and the guard suite (`tests/test_workflow_guards.py`) plus
dispatch-forms (`scripts/check_dispatch_forms.py`, run by `make check-dispatch-forms`) pull it under
several contracts it does not yet carry. Making unit tests green means carrying ALL of them; the
failures enumerate themselves when you run the file.

## The dispatchable filter is mechanical — adding a dispatch flips it ON

`_dispatchable()` = every `*.yml` whose `on:` contains `workflow_dispatch`. Adding a manual
re-judge path to a `workflow_run` workflow silently makes it dispatchable, so all four guard tests
AND the dispatch-forms checks now apply to it.

## The guard contracts a dispatchable workflow must satisfy

1. **A guard step** (`test_every_dispatchable_workflow_has_the_guard`): a step whose `run:` greps
   `/collaborators/` and `permission`.
2. **Byte-identical body** (`test_every_guard_step_is_byte_identical`): the guard step's
   `{name, env, run}` must be byte-identical (after `yaml.safe_dump(sort_keys=True)`) across every
   dispatchable workflow — copy an existing one VERBATIM (scope.yml, queued-alarm.yml), do not
   paraphrase. The count is derived: `len(guard_steps) == len(_dispatchable())+1` (all dispatchable +
   the guarded-but-undeclared ci.yml).
3. **Actor + write-level** (`test_the_guard_checks_both_actors_and_a_write_level`): the step checks
   BOTH `github.actor` and `github.triggering_actor`, and its `case` arm's accepted set is exactly
   `{admin, maintain, write}` (reads the DECISION arm, not substrings, and not the curl-204 form).
4. **It actually gates** (`test_the_guard_actually_gates_the_work`): a `guard` job (or a guarded
   step) that other jobs `needs`, so the working job depends on the guard.
5. **Dispatch-forms** (`make check-dispatch-forms`): the file needs a `# Trigger surface:`, `# Flow:`,
   `# Never:` header block; every `workflow_dispatch` input needs a `description:` AND a `default:`
   or `required: true` (else "meaning undefined when left empty"); and the docs/BOTS.md dispatch
   table must carry a row — run `make dispatch-forms-report` to PRINT the table, then paste it
   between the `<!-- dispatch-forms:begin -->` / `end` markers (the target only prints; it does not
   write).

## The dual-trigger guard shape

The scope.yml precedent: a workflow can be BOTH machine-triggered (`pull_request`/`workflow_run`)
AND manually dispatchable, and the SAME guard job gates both paths (it is the one byte-identical
guard every dispatchable workflow carries; the tests do not require it to be dispatch-only). Make
the working job `needs: [guard]`. For a `workflow_run` workflow the actor is whoever triggered the
original CI run — the owner/bot allowances in the guard cover the repo's actors.

## Docs and tests: what to run before push

```
# reproduce the six known failures first (they enumerate all missing contracts)
PYTHONPATH=scripts python3 -m pytest tests/test_workflow_guards.py \
  tests/test_dispatch_forms.py tests/test_issue_bot_manual_pick.py -q
# full related files (84 tests in the #1886 fix)
PYTHONPATH=scripts python3 -m pytest tests/test_workflow_guards.py tests/test_dispatch_forms.py \
  tests/test_issue_bot_manual_pick.py tests/test_ci_verdict.py -q
make check-dispatch-forms   # 26 dispatchable workflows OK after the add
```

## A workflow_run consumer's own red is NOT the PR's regression

A `workflow_run`-triggered workflow reads its file from the DEFAULT branch, not the PR head — so
while a PR is open, the `ci-verdict` row on the PR head is produced by the OLD (main) version of the
workflow. A green PR showing `ci-verdict: failure` is often that old workflow correctly holding the
PR's CI run to its rolled failure (e.g. scanner-images docker-build timeout) — sail the log before
blaming the PR: the verdict summary names the ONE failed job. Do not "fix" ci-verdict's own red on
a PR head; it is the gate working.

## A tick's (proven: …) must name the run, not the verdict prose (#745)

`check-pr-acceptance` rejects a tick whose `(proven: …)` carries only prose (e.g. `reviewer verdict
#N @ <sha>`): a tick is only as honest as the run behind it — it must name a CI run (`run=<id>`) or
a reproducible `proven: <command> rc=<n> <sha>`. Re-running the guard after a tick reds the SAME
items again for this reason, so a "fresh run" does NOT clear a verdict-prose tick; only a reviewer
re-write-back with real run/command evidence does. Route the re-tick to the reviewer lane (#1644) —
never self-tick.

## The planner's one-vehicle rule on the fix

Fix on the EXISTING branch (the same vehicle, #824), never a new branch. Push as a clean
fast-forward (fetch the live fork tip first — the rebase lane may have moved it), one atomic commit,
never merge/arm (#1088).
