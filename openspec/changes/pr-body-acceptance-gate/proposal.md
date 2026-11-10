# pr-body-acceptance-gate

## Why

Nothing in the judged CI set reads a PR BODY's own acceptance checklist. `check-pr-acceptance` (#1792)
reads the LINKED ISSUE's `## Acceptance criteria`; `check-pr-acceptance-form` (#1796) only requires the
PR body to CARRY a checklist, never that its boxes are ticked. So an engine-bump PR — which generates
its own checklist and closes no issue, making the PR body the SOLE vehicle for its acceptance record —
merges with all its boxes still `- [ ]`. Measured on PR #2267 (merged 2026-11-09T05:49:50Z via armed
auto-merge): all four boxes unticked, `ci-verdict` SUCCESS, and the published-pin criterion was in fact
**false at the head** (`[pins] NOT PUBLISHED` 404) — the manifest only arrived after the post-merge
`engine-build push=true`. Same shape on #2263–#2268. #1644 fixed the issue-body write-back path; a PR
body has no write-back seam, so an unticked PR-body box must be RED at the head, not silently passed.

## How

Add a judged body-gate to `scripts/check_pr_acceptance.py` (`body` subcommand + a pure
`pr_body_acceptance_findings`), a `make check-pr-acceptance-body` target, and a step in the ci.yml
`guard` job (a row of the ci-verdict judged set) and the scope.yml guard. The gate is scoped to when
the PR body is the SOLE vehicle for its checklist: when the PR (body + squash text) closes no issue and
carries its own `## Acceptance criteria` `- [ ]` checklist. In that scope:

- any `- [ ]` box at the head → RED (`acceptance-body-unchecked`);
- a `- [x]` box that names no CI run and no reproducible `command + rc=<n> + <sha>` → RED
  (`acceptance-body-tick-unprovable`, the #1858 evidence rule on the body side).

A PR that closes an issue is skipped by this gate — that issue carries the acceptance record and
`check-pr-acceptance` verifies it. Absence of a checklist is `check-pr-acceptance-form`'s finding, not
this gate's.

## Benefits

- auto-merge cannot arm on a `ci-verdict` that ignored an unticked PR-body box (the #2267 class);
- a pins-PUBLISHED bump PR that ticks its own boxes with run ids is still green (the gate does not
  reject a correct implementation);
- the #1644 issue-body write-back path and the form/presence gate are untouched.

## Success criteria

- [ ] `ci-verdict`'s judged set contains the PR-body acceptance gate — the step is in the ci.yml
      `guard` job and `guard` is a row of the ci-scope judged job table at the fixing head
- [ ] a bump PR with all four boxes unticked at its head is RED (real #2267 payload, no mock)
- [ ] a bump PR whose boxes are ticked with run ids at the head is GREEN
- [ ] a PR body that closes an issue is skipped (its checklist is not the sole vehicle), and #1644's
      issue-body path still passes (existing tests unchanged)
- [ ] change-note trio (`agent-wiki/`, `docs/changes.d/`, `CHANGES.md`) + the make help line
