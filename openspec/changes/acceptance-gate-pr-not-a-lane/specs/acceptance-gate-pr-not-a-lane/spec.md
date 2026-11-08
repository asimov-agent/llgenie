# acceptance-gate-pr-not-a-lane

## ADDED Requirements

### Requirement: a pull request is never a rollout lane

`check_pr_acceptance`'s rollout-lane population MUST exclude referenced numbers that are pull
requests, whatever their state. The issues API answers `state: open` for a PR, so a PR that cites the
umbrella it implements would otherwise register as that umbrella's own open lane and hold its own
close (measured on #1696 → #1558/#1694, run `42440654316` job `128608975606`).

[comment]: # (AC / how to verify: `test_open_pull_request_citing_the_umbrella_is_not_a_lane` reds on the pre-fix script and passes on the fixed one.)

#### Scenario: an OPEN pull request that cites the umbrella back does not hold the close

- **Given** an umbrella whose `## Acceptance criteria` are all ticked and whose body cites `#N`
- **And** `#N` is an OPEN pull request whose body cites the umbrella back
- **When** `check_pr_acceptance` evaluates a PR body that closes the umbrella
- **Then** the gate emits no `rollout-lane-open` finding for `#N` and exits 0

#### Scenario: an OPEN issue lane that cites the umbrella back still holds (#1859)

- **Given** the same umbrella, but `#N` is an OPEN issue that cites the umbrella back
- **When** `check_pr_acceptance` evaluates the closing PR body
- **Then** the gate emits `rollout-lane-open` and exits non-zero — the #1859 behaviour is unchanged

### Requirement: an already-closed close target is never lane-probed

When a `closes #N` target is already `CLOSED` (or a merged PR, reported as `MERGED`), the gate MUST
NOT derive rollout lanes from it: an already-closed umbrella cannot be closed prematurely, so the
probe reports a control that cannot fire (measured #1694, CLOSED 2026-11-04T21:09:51Z, flagged by a
2026-11-08 run). The `acceptance_verdict` half MUST keep running on that target.

[comment]: # (AC / how to verify: `test_already_closed_close_target_yields_no_lane_finding` reds on the pre-fix script and passes on the fixed one.)

#### Scenario: a closed target citing an open lane yields no lane finding

- **Given** a PR body that closes `#N`, and `#N` is CLOSED
- **And** `#N`'s body cites an OPEN issue lane that cites `#N` back
- **When** `check_pr_acceptance` evaluates the PR body
- **Then** no `rollout-lane-open` finding is emitted and the gate exits 0

#### Scenario: an unticked criterion on a closed target is still reported

- **Given** a CLOSED close target whose `## Acceptance criteria` carry an unticked item
- **When** `check_pr_acceptance` evaluates the closing PR body
- **Then** the `acceptance-unchecked` finding is still emitted (the #1792/#1858 verdict is unchanged)
