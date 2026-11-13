## ADDED Requirements

### Requirement: Cancel-refusal retirement — the cancel endpoint outranks the stale list row

The zero-job-pending monitor SHALL treat a fix-mode cancel refusal `already completed` as proof the
candidate is concluded: it SHALL file ONE deduped retirement record carrying the marker
`<!-- zero-job-zombie-retired: run N -->` (rendered through the one issue-body renderer), SHALL NOT
file a stranded issue or force a RED check-run for it, and SHALL NOT count it as a finding. Every
later scan SHALL read the retirement markers (issues open OR closed) and report matching candidates
as `zombie-retired` — named, never counted, never cancelled, never filed. The gate SHALL exit 0 when
every candidate is retired and SHALL stay red for live starvation. (`check-zero-job-pending`,
issue #2600)

#### Scenario: Confirmed phantoms clear the gate

- **WHEN** fix mode cancels candidates and every cancel is refused `already completed`
- **THEN** the run exits 0, prints a `zombie-retired` line naming each run, files retirement
  records carrying the retirement marker, and delivers no stranded issue or RED check-run

#### Scenario: A retired run is never re-counted

- **WHEN** a later read-only scan lists a run whose retirement marker exists in any issue
- **THEN** it is reported as `zombie-retired` and the gate exits 0 with no findings

#### Scenario: Live starvation keeps the old behavior

- **WHEN** a candidate's cancel lands (or its runner arrives at cancel time, or a delivery fails)
- **THEN** cancel/file/RED and the exit codes behave exactly as before (#1410/#1704)
