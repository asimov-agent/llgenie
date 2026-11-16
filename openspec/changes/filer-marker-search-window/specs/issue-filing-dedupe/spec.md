## ADDED Requirements

### Requirement: Marker-keyed filer dedupe searches the whole open board

A bot filer that files one issue per store revision SHALL find its previously filed issue by
searching issue bodies for its exact dedupe marker, regardless of how many issues are open or
where the marker-bearing issue ranks in a newest-first listing. A bounded listing window SHALL NOT
be the filer's memory: an open issue outside the window MUST still be found and updated instead of
a duplicate being created.

#### Scenario: Marker issue sits past the old 100-issue window

- **WHEN** the open board holds more than 100 issues and the issue carrying the store's marker
  ranks past position 100 newest-first
- **AND THEN** the filer runs for that same store revision
- **THEN** it finds the marker-bearing issue through the body search
- **AND** it updates that issue's body (REST path, #2673) and re-queues its label when missing
- **AND** it creates no new issue.

#### Scenario: No marker yet — create exactly once

- **WHEN** the body search for the marker returns no open issue
- **AND THEN** the filer runs for that store revision
- **THEN** it creates one issue carrying the marker and labels it through the REST path (#724).

#### Scenario: Search infrastructure fails — the step is loud, never silent

- **WHEN** the body search call itself fails (API error, malformed response)
- **AND THEN** the filer runs
- **THEN** the step fails with a named error rather than falling through to the create path
  (a filer that cannot read its memory must not file blind).
