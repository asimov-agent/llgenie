# docs-audit-record spec delta

## ADDED Requirements

### Requirement: The clean-audit record has a named durable home

The docs lane's audit playbook SHALL name issue #1645 as the durable recording home. A clean (or
fully-routed) audit pass SHALL post its record as a comment on #1645 carrying the measured-at sha
(bare, greppable), each check's gate rc, and the routing of any finding. The lane SHALL NOT open a
new tracker for the record and SHALL NOT substitute a planner DM while #1645 is open; the DM
fallback applies only when #1645 itself is closed.

#### Scenario: clean pass lands on the tracker, not in a DM

- **WHEN** the bounded own-domain audit runs at tip `<sha>` with all three checks green
- **THEN** #1645 carries a comment containing `re-audited at <sha>` plus the measured gate rcs

#### Scenario: no new tracker is invented

- **WHEN** an audit needs a record home and #1645 is open
- **THEN** the record is a comment on #1645 and no new tracking issue is filed

### Requirement: Findings route through the queue and cite the tracker

Each audit finding SHALL be its own six-section `agent:implement` issue naming #1645 and the
measured sha, routed through the normal implementation queue and never implemented by the auditing
pass. A finding already named under a standing umbrella (the live-vs-tree drift family) SHALL cite
that umbrella in the record instead of filing a duplicate one-off.

#### Scenario: a fresh finding gets its own routed issue

- **WHEN** a check surfaces an untracked gap
- **THEN** a six-section issue exists naming #1645 and the drift, and the audit pass implemented
  nothing

#### Scenario: an umbrella-named finding is cited, not refiled

- **WHEN** the surfaced drift is already measured under an open umbrella issue
- **THEN** the record cites the umbrella with the fresh measurement and no duplicate issue is filed
