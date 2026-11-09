# refuse an unrunnable task shape at the moment it is authored (issue #2123)

An implementation task was filed onto `llgenie-planner` (the orchestrator, which never
implements — it triages, refines and dispatches) with a `scratch` workspace (which has no
checkout to edit). Either fault alone made the task incapable of producing a PR; together they
parked the #2089 carry blocked for 51 minutes until a human-side reclaim noticed, because nothing
refused the bad assignment when it was written and a misassignment that is only caught by reading
history is, until then, real queued work that can never be started.

## What changed

**1 — the creation-time guard (`scripts/check_task_shape.py`).** A proposed task shape has two
facts that must agree: WHO is assigned (a lane that can act on the work class) and WHERE it works
(a workspace with a checkout when the task must produce a branch). The pure `refuse()` function
rejects either broken shape and names the offending FIELD in each message so the creator can fix it
in one read:

- **assignee** — a branch-producing task assigned to `llgenie-planner` is refused, quoting the role
  split ("the planner triages, refines and dispatches; it never implements") and naming the lane
  that owns the class.
- **workspace** — a branch-producing task in a `scratch` workspace is refused, naming
  `--workspace worktree` (or `dir:<existing-worktree>` when the branch already exists) as the
  remedy. Non-branch work (research, a report, a raw measurement) is not refused for scratch: a
  read has no branch to build.

The four work classes and their owning lanes — implementation → `llgenie-issse-implementer`,
docs → `llgenie-documentation-maintainer`, pipeline → `llgenie-ci-pipelines-maintainer`, rebase →
`llgenie-pr-merge-conflict` — are the role split recorded in the planner's SOUL, surfaced by the
`owners` subcommand.

**2 — the orchestrator pass-report leg (`scan`).** `scan` reads a `kanban list --json` dump and
prints a `MISASSIGNED <id>` line per BLOCKED task whose assignee cannot do its work class (the
shape that slipped past the pre-fix guard), exiting 1 when any is found — so an old misassigned
task is surfaced as a defect instead of silently left in the pool.

**3 — hermetic tests (`tests/test_check_task_shape.py`).** Nine tests drive the REAL `refuse()`
and `scan` CLI (no mocks of the product, only fixture text and board JSON): each refusal fires and
names its field, every work class is refused on the planner and on scratch, and the NEGATIVE
CONTROL — a legitimately-assigned implementation task (`llgenie-issse-implementer` + `worktree`) —
is still accepted. Owner-table assertions are subset checks, so a legitimate later addition to the
role split cannot red them.

## Verification

- `pytest tests/test_check_task_shape.py` → 9 passed (green with the negative control).
- `check-package-layers` → OK (157 modules, 0 cycles — `check_task_shape` registered).
- `check-architecture-census` → OK (referent an ancestor of HEAD).
- `check-docs` → green with this note + its fragment row.
