# Acceptance-writeback — the seam refuses evidence it cannot vouch for

## ADDED Requirements

### Requirement: a verdict-ref must name evidence the seam can vouch for

`acceptance_writeback.tick_acceptance` refuses a verdict reference that carries no proof
anchor. A verdict-ref must name a head sha (`[0-9a-f]{7,40}`) AND, when it names a
`run=<id>`, that run must have concluded `success` (the live `writeback` command and
`review_finalize finalize` consult `gh api repos/<repo>/actions/runs/<id>` through the
`--gh` seam before writing anything).

#### Scenario: a verdict-ref names a red run

Given `review_finalize.py finalize --verdict-ref '… run=42 …'`
When the live lookup of run 42 reports conclusion `failure` or `cancelled`
Then the seam raises `BodyError` naming the run and its conclusion
And no tick is written to the issue body

#### Scenario: a verdict-ref names no head sha

Given a `--verdict-ref` with reviewer/comment text but no 7–40 hex sha
Then `tick_acceptance` raises `BodyError` before touching the body
And the offline `apply`/`check` commands enforce the same grammar without any network read

#### Scenario: a green run at the measured head

Given `review_finalize.py finalize --verdict-ref 'reviewer=rr comment=1 head=<live-sha> run=<green-run>'`
When the live lookup of that run reports conclusion `success`
And the named head sha equals the PR head at measurement time
Then the tick is written exactly as before (#1644 append-only semantics unchanged)

### Requirement: the finalize path is verification-first

`review_finalize.py finalize` validates the verdict-ref (conclusion + head equality against
its own live `--head` observation) BEFORE the tick mutation, so the reviewer leg cannot
stamp a tick that the acceptance gate would immediately red-flag as `tick-cites-red-run` or
`tick-stale-head-unflagged`.

#### Scenario: finalize at a moved head

Given a finalize call whose `--verdict-ref` head sha is not the live PR head
And `--allow-head-moved` was NOT passed
Then finalize refuses the write (its existing head-moved guard extended to the run lookup)

#### Scenario: --dry never looks green-proof

Given `review_finalize.py finalize --dry`
Then no write is attempted and refusal reasons are still reported
