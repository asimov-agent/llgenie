# Refuse an unrunnable task shape at creation — tasks

- [x] `scripts/check_task_shape.py`: pure `refuse()` rejects a branch-producing task assigned to
      `llgenie-planner` (quoting the role split, naming the owning lane) and one in a `scratch`
      workspace (naming `--workspace worktree` / `dir:<existing-worktree>`), each naming the field
- [x] `scripts/check_task_shape.py`: `owners` prints the four work-class → owning-lane table (AC-5)
- [x] `scripts/check_task_shape.py`: `scan` surfaces a BLOCKED task whose assignee cannot do its class
      (orchestrator pass report, AC-4), exiting 1 when any found
- [x] `tests/test_check_task_shape.py`: 9 tests — both refusals fire and name their field, every work
      class is refused on the planner and on scratch, and the NEGATIVE CONTROL
      (`llgenie-issse-implementer` + `worktree`) is accepted
- [x] register `check_task_shape` in `scripts/package-layers.json`
- [x] change-note trio keyed to #2123: `agent-wiki/2026-11-08-refuse-unrunnable-task-shape.md`,
      `docs/changes.d/` fragment, `CHANGES.md`
- [x] guard-prove: run the 9 refusal tests red-then-green
- [x] `make openspec-validate NAME=refuse-unrunnable-task-shape` green
