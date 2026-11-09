# Fix: kanban must refuse an implementation task assigned to the planner or left in a scratch workspace

## Why

A lane filed an implementation task onto `llgenie-planner` (the orchestrator — triages, refines,
dispatches, never implements) with a `scratch` workspace (no git checkout to edit). Either fault
alone made the task incapable of producing a PR; together they parked the #2089 carry blocked for
51 minutes — created `2026-11-08 04:37` by `llgenie-engine-improver` as `t_fe3d094f`, reclaimed at
`05:28` (`run 528`, `manual: True`, reason "planner never implements: an implementation task (#2089)
was created with --assignee llgenie-planner and a scratch workspace…"). Nothing refused the bad
assignment when it was written; `hermes kanban dispatch` reported `Spawned: 0` and only a human
reading the history noticed.

The board stops representing who owes what when a lane can park a task on a profile that cannot act
on it: a misassigned task is indistinguishable from real queued work until a reclaim reads it, and a
task in a scratch workspace can never produce a branch regardless of who picks it up.

## What changes

`scripts/check_task_shape.py` is the creation-time guard. The pure `refuse()` function is the single
decision point; a task is *branch-producing* when its title matches one of the fleet's four work
classes (implementation, docs, pipeline, rebase), and a shape is refused when either fact is broken
— each message names the offending FIELD — while non-branch work (research, a report) is not refused
for a scratch workspace: a read has no branch to build.

- A branch-producing task assigned to `llgenie-planner` is refused, quoting the role split
  ("the planner triages, refines and dispatches; it never implements") and naming the lane that owns
  the class.
- A branch-producing task in a `scratch` workspace is refused, naming `--workspace worktree`
  (or `dir:<existing-worktree>` when the branch already exists) as the remedy.
- `scan` reads a `kanban list --json` dump and prints one `MISASSIGNED <id>` line per BLOCKED task
  whose assignee cannot do its work class (the shape that slipped past the pre-fix guard), exiting 1
  when any is found — the orchestrator pass report surfaces an old misassignment as a defect instead
  of leaving it in the pool.
- `owners` prints the four work classes and their owning lanes, so the refusal and the role split
  agree in one read.

The four classes and their owning lanes are recorded as the role split (AC-5), not a new authority:
implementation → `llgenie-issse-implementer`, docs → `llgenie-documentation-maintainer`,
pipeline → `llgenie-ci-pipelines-maintainer`, rebase → `llgenie-pr-merge-conflict`.

`tests/test_check_task_shape.py` drives the REAL `refuse()` and `scan` CLI (no mocks of the product,
only fixture text and fixture board JSON): each refusal fires and names its field, every work class
is refused on the planner and on scratch, and the NEGATIVE CONTROL — a legitimately-assigned
implementation task (`llgenie-issse-implementer` + `worktree`) — is still accepted. Owner-table
assertions are subset checks, so a legitimate later addition to the role split cannot red them.

SCOPE OUT: no reassignment of existing cards, no live job-prompt or planner-SOUL edits (that is a
separate issue), no change to the queue mechanism. The guard is where creation happens; wiring it
into the planner's create path and the pass report is a follow-on the fleet can adopt safely because
the decision point is a single pure function.

## Who

The fix belongs to the implement lane (`llgenie-issse-implementer`), which owns the refusal and the
test, wired into the board's creation seam so a misassignment is refused when it is written, never
51 minutes later in a reclaim.

## Changes

- ADD `scripts/check_task_shape.py` (refuse / scan / owners CLI)
- ADD `tests/test_check_task_shape.py`
- Register the module in `scripts/package-layers.json`
- Change-note trio: `agent-wiki/2026-11-08-refuse-unrunnable-task-shape.md`, `docs/changes.d/…`,
  `CHANGES.md`
