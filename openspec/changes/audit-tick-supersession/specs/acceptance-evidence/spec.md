# Spec delta: acceptance-evidence (audit-tick-supersession)

## MODIFIED Requirements

### Requirement: The acceptance-tick audit counts only unsuperseded stale ticks

The repo audit tool (`scripts/audit_acceptance_ticks.py audit`) pages every
closed issue, collects every ticked criterion citing `run=<id>`, and looks up
each cited run's live conclusion and head. A criterion is stale only when none
of its cited runs is `completed/success` AND the issue carries no supersession
note covering it. A criterion is covered when the issue has a comment starting
with the `<!-- SUPERSEDE-2288 -->` marker whose `cited:` lines name the
criterion's line and its run ids. The audit reports the stale count, the
counting method, and exits 0 only when the stale count is 0.

#### Scenario: a superseded criterion leaves the denominator

- **WHEN** a closed issue's ticked criterion cites only a red run and the issue
  carries a `SUPERSEDE-2288` note naming that criterion and run id
- **THEN** the audit excludes it and reports it under `superseded`, not `stale`

#### Scenario: a tick citing any green cited run is never stale

- **WHEN** a ticked criterion cites runs of which at least one is
  `completed/success`
- **THEN** the audit counts it honest regardless of supersession notes

## ADDED Requirements

### Requirement: Supersession notes are rendered by one renderer and posted append-only

`scripts/audit_acceptance_ticks.py` renders every supersession comment body via
`render_supersede_note` — the only place the note's shape exists — keyed to the
issue's recorded (`AUDIT-2288`) criteria and cited run ids, stating the measured
run conclusion, that the tick is not rewritten, and that future acceptance is
governed by the #2288 machinery. `post` skips any issue that already carries
the marker and never edits an issue body or any existing comment.

#### Scenario: posting is idempotent

- **WHEN** `post` runs twice against an issue with a stale criterion
- **THEN** exactly one `SUPERSEDE-2288` comment exists afterwards

#### Scenario: notes are never hand-built

- **WHEN** any producer posts a supersession note
- **THEN** the body came from `render_supersede_note`, verbatim
