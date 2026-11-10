# pr-body-acceptance-gate

## ADDED Requirements

### Requirement: a PR whose own acceptance checklist is the sole vehicle is held to it at its head

When a PR body closes no issue (neither in the body nor in the joined squash commit messages) and its
body carries its own `## Acceptance criteria` `- [ ]` checklist, that checklist is the PR's SOLE
acceptance record (an engine-bump PR generates its own checklist; there is no linked issue to write
back to). The gate MUST be RED for that PR while any of its own boxes is `- [ ]` at its current head,
and RED for a `- [x]` box whose text names no CI run and no reproducible `command + rc=<n> + <sha>`
(the #1858 evidence rule). auto-merge must not arm on a verdict that ignored an unticked box (the #2267
class: all four boxes unticked, `ci-verdict` SUCCESS, the published-pin criterion false at the head).

[comment]: # (AC / how to verify: `test_engine_bump_all_boxes_unticked_is_RED` and `test_engine_bump_all_boxes_ticked_with_run_ids_is_GREEN` red/pass on the fixed script.)

#### Scenario: an engine-bump PR with all boxes unticked is RED

- **Given** an engine-bump PR body whose `## Acceptance criteria` carries four `- [ ]` boxes and that
  closes no issue
- **When** `check_pr_acceptance body` evaluates it at the head
- **Then** the gate emits `acceptance-body-unchecked` findings and exits non-zero

#### Scenario: an engine-bump PR whose boxes are ticked with run ids is GREEN

- **Given** the same engine-bump PR body, each criterion ticked `- [x]` and naming a CI run id
  (`run=<id>`)
- **When** `check_pr_acceptance body` evaluates it at the head
- **Then** the gate emits no blocking finding and exits 0

#### Scenario: a ticked box with no re-producible evidence is RED

- **Given** engine-bump PR body with a `- [x]` box whose text names no `run=` and no `rc=<n>` + sha
- **When** `check_pr_acceptance body` evaluates it at the head
- **Then** the gate emits `acceptance-body-tick-unprovable` and exits non-zero

### Requirement: a PR that closes an issue is not held by the body gate

When a PR body (or its squash text) closes an issue, that issue is the acceptance record for the
change and `check-pr-acceptance` (#1792) verifies it. The body gate MUST NOT also hold the PR's own
checklist — the two surfaces would double-count and a correct implementer PR (which carries a body
checklist AND closes its issue) would be red for no reason.

[comment]: # (AC / how to verify: `test_a_pr_that_closes_an_issue_is_skipped` passes on the fixed script; the existing test_check_pr_acceptance.py suite is unchanged.)

#### Scenario: a PR that closes an issue is not red on its own unticked body boxes

- **Given** a PR body that closes `#N` and carries its own partly-unticked `## Acceptance criteria`
- **When** `check_pr_acceptance body` evaluates it at the head
- **Then** the gate emits no `acceptance-body-*` finding and exits 0 — the issue-side
  `check-pr-acceptance` owns that PR

### Requirement: the gate is part of the judged set ci-verdict reads

The gate MUST be a step of the ci.yml `guard` job, and `guard` MUST be a row of the ci-scope judged job
table (`ci_scope.JOBS`), so a red body-gate reds the judged `guard` job, the judged CI run, and
consequently the `ci-verdict` check-run — auto-merge cannot arm on a verdict that ignored an unticked
box. scope.yml's guard MUST carry the same step for docs-only bot PRs.

[comment]: # (AC / how to verify: the step is present in .github/workflows/ci.yml `guard`; `ci_scope.JOBS` lists `guard`; `make verdict-roster` shows `ci.yml` judged. Read the workflow/job table at the fixing head — never a grep for a string that happens to exist.)

#### Scenario: a guard-body red on the engine-bump makes the judged CI run red

- **Given** an engine-bump PR whose `guard` job's `make check-pr-acceptance-body` step is red at the
  head
- **When** `ci-verdict` judges that finished CI run (an unticked box reds the `guard` job, a row of
  `ci_scope.JOBS`)
- **Then** the verdict posts `ci-verdict: failure` for the head, so auto-merge cannot arm

## MODIFIED Requirements

(none)
