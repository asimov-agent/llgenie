# Spec — the tick arms auto-merge (issue #2182)

## What changed

A delta from the #2159 procedure: `tick_board.sh` measures arm state in section B
and `arm_pr.sh` performs a single mechanical arm.

## ADDED Requirements

### Requirement: section B measures arm state per PR

The tick's `tick_board.sh` section B must report, for every open PR:
`autoMergeRequest` present/absent, `mergeStateStatus`, `mergeable` and
`reviewDecision`, and must classify each PR into exactly one of four states —
`armed`, `unarmed`, `armed-but-DIRTY` (inert), and `green+approved+unarmed` —
printing an `ARM armed=N unarmed=N armed-but-DIRTY(inert)=N` summary line.

#### Scenario: a known-armed PR is reported armed
Given a fixture PR list that includes a PR whose `autoMergeRequest` is present,
when `tick_board.sh` section B runs, the per-PR line and the `ARM` summary must
read `armed` — never `unarmed` (the omission of `autoMergeRequest` from the field
list is the false-measurement bug, not "nothing is armed").

#### Scenario: an armed DIRTY PR is reported inert
Given a fixture PR whose `autoMergeRequest` is present and `mergeStateStatus` is
`DIRTY`, section B must classify it `armed-but-DIRTY(inert)` and exclude it from
both the `armed` and the `unarmed` counts.

### Requirement: the tick arms green + approved + unarmed PRs

The tick must have an explicit ordered step that arms a `green+approved+unarmed`
PR with `gh pr merge <n> --squash --auto` and reads `autoMergeRequest` back,
reporting the arm time. The exit code of the arm command is never accepted as
proof.

#### Scenario: an arm that returns exit 0 but arms nothing is a failure
Given a PR whose head's base is not the default branch, when `gh pr merge --auto`
exits 0 but the read-back shows no `autoMergeRequest` (#964), the step must report
a hard failure ("NOT success") rather than claiming the PR is armed.

#### Scenario: the tick refuses to arm a live-run or mid-rebase head
Given a PR whose head has a `pending`/`queued`/`in_progress` check or is
mid-rebase (#2069), the step must refuse to arm it.

#### Scenario: an inert arm routes to the rebase lane and is never handled
Given a PR whose arm is present but inert (DIRTY/conflicting), the step must
report it as impossible, route it to `llgenie-pr-merge-conflict`, and never count
it as handled.
