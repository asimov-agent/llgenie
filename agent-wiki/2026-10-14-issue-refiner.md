# The issue-refiner: make the backlog implementable on the spare capacity (issue #263, PR #264)

## Why

The implementer (#248, and #261's decide-before-implementing path) only ever refines the ONE issue
it is about to implement. Nothing improved the *backlog* ahead of time, so missing acceptance
criteria, scope settled in an old comment, and issues that are actually duplicates were discovered
only by an agent that had already spent a branch and a run — one daily slot per discovery.

## What

- `scripts/issue_refiner.py` (stdlib only, `gh` on `PATH`): `count` (its own daily budget, from the
  `agent:refined` label), `pick`, `apply`.
- **Hourly, one issue per run**, and the only refusal is the race: `pick` yields while an issue is
  *waiting* for the implementer — labelled `agent:implement`/`agent:ready` with no PR linking it —
  and proceeds once that issue has a PR (work already started is not waiting for anyone). The
  decision lives in code rather than in a CI `if:` (issue #107).
- **Eligibility**: open, oldest first, skipping anything labelled `agent:refined` / `agent:closed` /
  `agent:implement` / `agent:ready`, and skipping an issue GitHub reports as linked to a PR
  (`closedByPullRequestsReferences`) — i.e. already implemented.
- **The agent reviews, it does not implement**: `refine-in.md` carries the thread plus the review
  instruction; the verdict goes to `refine.md` as `REFINE: refined` (with a required `RESTATED:`
  block) or `REFINE: already-clear` (with a reason).
- **The outcome is ONE comment plus the `agent:refined` label.** No branch, no PR, no issue-body
  edit — asserted from the recorded argv, because "never a PR" is this bot's defining constraint.
- `issue-refiner.yml`: schedule (four times a day, when the implementer's slots are normally spent)
  plus owner-guarded `workflow_dispatch`, concurrency 1, the agent running inside the agent image.

## Measured

- `tests/test_issue_refiner.py`: 7 passed — the budget query, the spare-capacity refusal, the
  eligibility skips (decided / claimed / already-PR'd), the rendered thread and instruction, the
  verdict grammar with its refusal, and the "one comment, one label, never a PR" argv.
- `make lint`, `make check-wiring`, `openspec-validate NAME=issue-refiner` all green with the
  change; README updated for the three new targets (issue #257's docs gate).
