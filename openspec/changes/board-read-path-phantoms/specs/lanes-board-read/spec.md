# Lanes board read — merged/closed PRs never surface as open reconcile work

## ADDED Requirements

### Requirement: the reconcile trigger re-verifies the PR before any reconcile action

A lane SHALL NOT take a reconcile action (rebase, amend, re-push, body edit, re-open) on a
PR-numbered red before reading `pulls/<n>` state. The instrument SHALL be
`make lane-reconcile-guard PR=<n>`, which reads `state`, `merged`, `mergedAt`, `mergeCommitSha`
and `headRefOid` for that PR and prints a single verdict line: `#<n> merged, read-only …`,
`#<n> closed, read-only …`, or `#<n> open, actionable …`. A `merged` or `closed` verdict means the
lane reports "merged, read-only" (or "closed, read-only") and performs NO reconcile.

#### Scenario: a merged PR's head-sha is presented for reconcile

Given a lane holds a red that names PR #1742 at head `8482c24b` (the 2026-11-05 phantom)
When the lane runs `make lane-reconcile-guard PR=1742`
Then the verdict line reads `#1742 merged, read-only` with the merge commit sha
And the lane emits "merged, read-only" instead of "red" and takes no reconcile action

#### Scenario: an open PR stays actionable

Given a PR whose `pulls/<n>` read shows `state=open`
When the lane runs `make lane-reconcile-guard PR=<n>`
Then the verdict line reads `#<n> open, actionable` with its `mergeStateStatus`
And the reconcile path proceeds as before

#### Scenario: no verdict without a read

Given `pulls/<n>` cannot be read (API failure, bad number)
When the guard runs
Then it exits non-zero and prints no verdict line — an unevidenced reconcile stays blocked

### Requirement: open-board reads name state per row

Lane board recipes that ask "what open work exists" SHALL request the row's `state` (and `merged`
where the read can carry it) — search-form reads name `is:open` in the query. A board row whose
PR reads `merged` or `closed` SHALL NOT be dispatched, claimed, or reconciled as work; it is
evidence, not work. Reads that intentionally span states (vehicle sweeps with `--state all`) SHALL
print the state next to each row they list.

#### Scenario: a merged row leaks into an open-work query

Given `gh search prs --repo asimov-agent/llgenie '1644'` returns merged and closed rows
When a lane lists open work from a search-form read
Then the query carries `is:open` and the lane states each surviving row's state
And a row that still names a merged/closed PR gets the guard verdict instead of a claim

#### Scenario: re-running the read path after the incident objects

Given the incident objects #1742 (squash `ebabd9f1`) and #1743 (squash `27d5477b`)
When the board read path is re-run at the current main tip
Then neither surfaces as open work (each answers `merged, read-only`)

### Requirement: the guard is script-backed, single-path, and tested

`scripts/pr_reconcile_guard.py` SHALL be the only implementation of this verdict (stdlib only, the
GitHub API only through `gh` on PATH), wired as `make lane-reconcile-guard` (host-only lane tool,
recorded in the host-only wiring fixture), registered in `scripts/package-layers.json`, documented
in `docs/BOTS.md`, and covered by `tests/test_pr_reconcile_guard.py` for the merged, closed, open,
and read-failure states.

#### Scenario: a lane hand-rolls the check instead

Given the guard target and script exist
When the fleet recipe text is read
Then every reconcile-trigger recipe names `make lane-reconcile-guard` as the pre-action read
And no recipe re-implements the `pulls/<n>` state probe inline
