# sweep-bot-dispatch

## MODIFIED Requirements

### Requirement: the trigger guard MUST admit the repository's own bot on a workflow_dispatch of this repository

The shared `Owner / collaborator trigger guard` (byte-identical across every workflow that carries it)
admits the repository owner, a collaborator with write access, and the repository's own bot. Before
this change the bot was admitted ONLY when the run's head repository equaled this repository (a
same-repo PR head, #510). This requirement extends that allowance: the bot is also admitted when the run
is a `workflow_dispatch` of this repository — `github.event_name == workflow_dispatch`. A
`workflow_dispatch` can only be started by a token with write access to THIS repository and can only
target THIS repository's own refs (a fork cannot dispatch our workflows and cannot add refs here), so
the event itself carries the same-repo-head guarantee that the `HEAD_REPO` check provides on PR events.
The weekly all-pipelines sweep dispatches every active workflow with the repo's `actions: write` token,
making the actor the bot on a `workflow_dispatch` with no head repo; this carve-out lets the sweep
verify its targets instead of redding by design. The order and the refusal branch are otherwise
unchanged: a bot acting as the actor of a foreign PR head (`HEAD_REPO != REPO`), or acting on a
non-dispatch event with no head repo, still falls through to the collaborator permission check and is
refused.

WHEN a `workflow_dispatch` run arrives at a target workflow
AND its actor or triggering_actor is `github-actions[bot]`
THEN the guard admits it (the event is the same-repo guarantee; a foreign actor cannot trigger our
dispatch)
AND the guard still refuses the bot on a foreign PR head and on a non-dispatch event.

#### Scenario: the sweep's own dispatch of the six targets passes the guard

- **Given** the real guard script of a guarded workflow, `EVENT=workflow_dispatch`, and the actor is
  `github-actions[bot]`
- **When** the guard runs
- **Then** it exits 0 and prints an allowance, because the repo's own dispatch path (used by the weekly
  all-pipelines sweep) is this repository's automation driving its own workflows
- **Test:** `tests/test_workflow_guards.py::test_the_bot_passes_on_workflow_dispatch_of_this_repo`

#### Scenario: a bot on a non-dispatch event with no head repo is still refused (negative control)

- **Given** the real guard script, a `schedule` event (no head repo), actor `github-actions[bot]`
- **When** the guard runs
- **Then** it exits 1 and prints `Refused` — the carve-out is event-scoped; only the repo's own
  dispatch path earns it, so the #495/#510 foreign-head / non-dispatch guarantee is not weakened
- **Test:** `tests/test_workflow_guards.py::test_the_bot_still_refused_on_a_non_dispatch_event_with_no_head`

## ADDED Requirements

### Requirement: the sweep SHALL name a workflow it could not verify, with the reason

When a dispatched run still fails at its own trigger guard — a workflow that carves no bot path — the
sweep's table must not show a bare `completed/failure` as if the pipeline ran and failed. It names the
workflow and the cause: the run died at its own trigger guard (the repository bot was refused before any
pipeline work ran).

WHEN a dispatched run concludes `failure`
AND the run's own trigger guard is the failing job
THEN the sweep renders that workflow's row as `NOT VERIFIED — refused at its own trigger guard` (naming
the workflow and the reason), never a bare `completed/failure`.

#### Scenario: a guard-refused run renders as NOT VERIFIED, not as completed/failure

- **Given** a dispatched run that concludes `failure` with its trigger guard the failing job
- **When** the sweep renders the report
- **Then** the workflow is named with the reason `refused at its own trigger guard` and the cell is not
  `completed/failure`
- **Test:** `tests/test_all_pipelines.py::test_guard_refused_run_is_named_not_bare_failure`

### Requirement: the sweep SHALL dispatch targets at the ref it is running from

The umbrella sweeps the tree it is running, not a different sha: it dispatches each target at its own
current ref (`github.ref_name`) instead of a hardcoded `main`, so a PR-head sweep exercises the PR-branch
workflows (whose trigger guard carries the carve-out) and a weekly-on-main sweep exercises main.

WHEN the all-pipelines workflow runs
THEN it dispatches each target at `github.ref_name` (the ref the sweep itself is running from).

#### Scenario: the sweep step dispatches each target at the ref it is running from

- **Given** `.github/workflows/all-pipelines.yml` running at a PR head branch
- **When** the sweep step runs `make all-pipelines-sweep`
- **Then** it passes `REF="${{ github.ref_name }}"` so targets are dispatched at that same ref
- **Test:** the workflow file's sweep step env carries `REF: ${{ github.ref_name }}`

