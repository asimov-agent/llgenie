# Refuse an unrunnable task shape at creation

## ADDED Requirements

### Requirement: A branch-producing task assigned to the planner is refused

When a task is branch-producing (its title matches one of the fleet's four work classes) and its
assignee is `llgenie-planner`, the creation guard MUST refuse it and MUST name the role split — the
planner triages, refines and dispatches; it never implements — and the lane that owns the work class.

#### Scenario: an implementation task assigned to the planner is refused, naming the owner

Given an implementation-class title ("implement #2089 as a reviewable PR: open a branch and author
the code") and an assignee of `llgenie-planner` with a `worktree` workspace,
When `refuse()` reads the shape,
Then it returns at least one reason, the reason names the `assignee` field, names
`llgenie-issse-implementer` as the owning lane, and states that the planner never implements.

- **Test:** `tests/test_check_task_shape.py::test_assignee_refusal_names_field_and_owner`

#### Scenario: every work class is refused on the planner

Given one title per work class (implementation, docs, pipeline, rebase),
When `refuse()` runs with `llgenie-planner` as assignee,
Then each returns a refusal and no work class is treated as "belongs to the planner".

- **Test:** `tests/test_check_task_shape.py::test_refuse_across_every_work_class`

### Requirement: A branch-producing task in a scratch workspace is refused

When a task is branch-producing and its workspace kind is `scratch` (or unspecified, which defaults
to scratch), the creation guard MUST refuse it and MUST name `--workspace worktree` (or
`dir:<existing-worktree>` when the branch already exists) as the remedy, because a scratch workspace
has no checkout to edit.

#### Scenario: a branch-producing task in a scratch workspace is refused, naming the remedy

Given an implementation-class title and an assignee of `llgenie-issse-implementer` with a `scratch`
workspace,
When `refuse()` reads the shape,
Then it returns at least one reason, the reason names the `workspace` field and the `worktree` /
`dir:<existing-worktree>` remedy.

- **Test:** `tests/test_check_task_shape.py::test_workspace_refusal_names_field_and_remedy`

#### Scenario: an unspecified workspace defaults to scratch

Given a workspace value of `None`, `""` or `"scratch"`,
When `workspace_default()` normalises it,
Then it returns `scratch`, while an explicit `worktree` stays `worktree`.

- **Test:** `tests/test_check_task_shape.py::test_specified_workspace_defaults_to_scratch`

#### Scenario: non-branch work is not refused for a scratch workspace

Given a task whose title carries no work-class marker (research, a report),
When `refuse()` reads it with a `scratch` workspace,
Then it returns no refusal: a read has no branch to build.

- **Test:** `tests/test_check_task_shape.py::test_non_branch_task_scratch_is_acceptable`

### Requirement: A legitimately-assigned implementation task is accepted

The negative control: a branch-producing task assigned to the lane that owns its class
(`llgenie-issse-implementer` for implementation) and given a `worktree` workspace MUST pass without
any refusal, proving the guard rejects bad shapes without rejecting good ones.

#### Scenario: the canonical implementation shape is accepted

Given an implementation-class title, an assignee of `llgenie-issse-implementer` and a `worktree`
workspace,
When `refuse()` reads the shape,
Then it returns an empty list.

- **Test:** `tests/test_check_task_shape.py::test_negative_control_legit_implementation_task_accepted`

### Requirement: The four work classes name the correct owning lanes

The role split is authoritative: implementation → `llgenie-issse-implementer`,
docs → `llgenie-documentation-maintainer`, pipeline → `llgenie-ci-pipelines-maintainer` and
rebase → `llgenie-pr-merge-conflict`, and no class is owned by the planner.

#### Scenario: every class has exactly its declared owner

Given the required class→owner table,
When it is compared against the recorded role split,
Then each class is present with its declared owner and none is owned by `llgenie-planner`.

- **Test:** `tests/test_check_task_shape.py::test_owner_table_names_every_class_owner`

### Requirement: A blocked misassigned task is surfaced by scan

The orchestrator-pass-report leg `scan` MUST read a `kanban list --json` dump and print one
`MISASSIGNED <id>` line per BLOCKED task whose assignee cannot do its work class, exiting 1 when any
is found — an old misassignment is surfaced as a defect instead of left in the pool — and MUST stay
silent (exit 0) on a clean board.

#### Scenario: a blocked misassigned task is surfaced, a correct one is not

Given a board JSON with a blocked planner-assigned scratch task `t_bad`, a blocked correctly-owned
worktree task `t_good`, and a running correctly-owned task `t_running`,
When `scan` runs on that JSON,
Then it exits 1, prints `MISASSIGNED t_bad`, and prints neither `t_good` nor `t_running`.

- **Test:** `tests/test_check_task_shape.py::test_scan_surfaces_a_blocked_misassigned_task`

#### Scenario: a clean board exits zero

Given a board JSON with only a correctly-owned blocked task,
When `scan` runs on it,
Then it exits 0 and prints no `MISASSIGNED` line.

- **Test:** `tests/test_check_task_shape.py::test_scan_clean_board_exits_zero`
