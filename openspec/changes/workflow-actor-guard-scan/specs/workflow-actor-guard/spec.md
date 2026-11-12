# workflow-actor-guard — Spec Delta

## ADDED Requirements

### Requirement: Every workflow file declares an explicit top-level token scope

Every file in `.github/workflows/` SHALL declare a top-level `permissions:` block, and the value
`write-all` SHALL never be used. A workflow without a top-level block inherits whatever the
org-wide default token scope is, which makes "who can make this run do privileged things"
unanswerable from the file; the gate SHALL refuse that state.

#### Scenario: A workflow with no top-level permissions block is refused
- **Given** a `.github/workflows/new.yml` whose document has no column-zero `permissions:` key
- **When** `make check-workflows` scans the directory
- **Then** a finding `workflow-permissions/<file>` is reported naming the file and rule

#### Scenario: write-all is refused
- **Given** a workflow carrying `permissions: write-all` at top level
- **When** the gate scans it
- **Then** a finding `workflow-write-all/<file>` is reported

#### Scenario: The existing fleet states its scope
- **Given** the 36 workflow files at `main` after `ci.yml` and `pipeline.yml` gained explicit
  top-level blocks preserving their jobs' current effective scope
- **When** `make check-workflows` runs
- **Then** it exits 0 with no `workflow-permissions` or `workflow-write-all` findings

### Requirement: pull_request_target is refused outright

No workflow SHALL trigger on `pull_request_target` — the trigger that runs fork code with
base-repo write credentials, which this repository has never used (measured: 0 uses at
`d8700c60e`). The gate keeps it that way.

#### Scenario: Adding pull_request_target reds the gate
- **Given** a workflow whose `on:` block carries `pull_request_target:`
- **When** `make check-workflows` runs
- **Then** a finding `workflow-forbidden-trigger/<file>/pull_request_target` is reported

### Requirement: Outsider-reachable triggers carry the owner/collaborator/bot guard, or derive it from guarded sources

A workflow whose trigger surface includes an event a non-collaborator can cause (`pull_request`,
`workflow_run`, `issues`, `issue_comment`, `pull_request_review`,
`pull_request_review_comment`, `label`, `discussion`) SHALL either (a) reference
`github.triggering_actor` outside any `run:` block — the inline trigger guard the fleet already
uses (owner / collaborator via the collaborators permission API / bot allowlist) — or (b) derive
the guard transitively: its only outsider-reachable trigger is `workflow_run` and every workflow
named in its `workflows:` roster is itself guarded (a) or internal-only. `workflow_run` cannot
start a run on its own authority; it follows the completion of a run whose entry the roster
workflows already gate. Triggers internal to the repository (`push`, `schedule`,
`workflow_dispatch`, `workflow_call`) SHALL NOT require the guard, because GitHub grants all four
only to write-capable accounts, repo-owned clocks, or repo-local callers.

The scan's scope is the whole **start surface** of the fleet (owner clarification 2026-11-12):
every `.github/workflows/*.yml` file is read and classified by how it can start — a pipeline that
starts AUTOMATICALLY when a PR is created (the PR-triggered CI and every `workflow_run` follower its
completion kicks off), one that starts on a MERGE TO MAIN (`push`), one started by a CRON schedule
(`schedule`), and one started MANUALLY by the owner or a collaborator (`workflow_dispatch`). For a
PR-triggered run `github.triggering_actor` IS the person who created or changed the PR, so
requiring the signature in those files is requiring the pipeline to prove its creator is the owner,
a collaborator, or the bot; a fork outsider may only ever reach the restricted read-only CI lane.
The other three start classes are already three-party-only at the platform level (push, cron and
dispatch all require write access or are repo-owned clocks), which is why they are classified
internal — the classification is the scan's answer to "who can start this", not an exemption.

#### Scenario: An open trigger without the guard is refused
- **Given** a `.github/workflows/rogue.yml` triggered on `issues` with no reference to
  `github.triggering_actor` outside `run:` blocks
- **When** `make check-workflows` runs
- **Then** a finding `workflow-actor-guard/rogue.yml` is reported

#### Scenario: A guard that exists only inside a run block does not count
- **Given** a workflow that mentions `github.triggering_actor` only inside a `run: |` script body
- **When** the gate applies the `run:`-block carve-out the file's existing expression discipline
  uses
- **Then** the same `workflow-actor-guard` finding is reported

#### Scenario: A workflow_run follower inherits the guard from its guarded roster
- **Given** a workflow triggered only on `workflow_run` whose roster names workflows that each
  satisfy the guard rule or are internal-only (the real `auto-merge.yml` naming CI + ci-scope, the
  real `zero-job-pending.yml` naming ci-requeue)
- **When** `make check-workflows` runs
- **Then** no finding is reported for the follower

#### Scenario: An unguarded roster source taints the follower
- **Given** a `workflow_run` follower whose roster names a workflow that has an open trigger and
  no guard of its own
- **When** the gate resolves the roster transitively
- **Then** findings are reported for BOTH the unguarded source and the follower

#### Scenario: Internal-only files need no guard
- **Given** the real `registry-liveness.yml` (push + schedule) and `pipeline.yml` (workflow_call)
- **When** `make check-workflows` runs
- **Then** neither carries an `workflow-actor-guard` finding

#### Scenario: The whole real fleet passes with zero exemptions
- **Given** all 36 workflow files at `main` after this change
- **When** `make check-workflows` runs
- **Then** it exits 0, and no exemption fixture entry is needed for any file

### Requirement: The rules run in the main CI pipeline with no new wiring

The rules SHALL live inside `make check-workflows`, which already runs in `ci.yml`'s required
`guard` job, in `scope.yml`'s docs gate, and in `make lane-preflight` — so every PR and every
lane validates the whole `.github/workflows/` directory before merge.

#### Scenario: A PR that adds an unguarded open-trigger workflow cannot merge
- **Given** a PR whose diff adds a workflow triggered on `issue_comment` with no guard
- **When** the PR's CI runs the `guard` job (`make check-workflows`)
- **Then** the guard job fails with the `workflow-actor-guard` finding and the PR is not mergeable
