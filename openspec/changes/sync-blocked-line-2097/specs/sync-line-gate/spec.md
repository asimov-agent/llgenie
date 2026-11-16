# sync-line-gate spec delta

## ADDED Requirements

### Requirement: The sync-line gate accepts a measured blocked line as the honest input

For a bot PR that edits `agents/<profile>/`, `make check-pr-sync-line` SHALL accept a
`SYNC-BLOCKED: <profile> #<issue> <measured reason>` body line (the reason carrying digits —
the measured file/byte counts) as satisfying that profile, in addition to the unchanged exact
`SYNC: <p> make sync-agent-profile PROFILE=<p>` line. The blocked line SHALL be honored only when
the block is real: when the profile's live home is readable the gate SHALL re-measure the
truncation with the same criterion `agent_profile_sync` refuses on (a differing file whose live
copy is larger) and SHALL red a claimed line the measurement does not support; when the live home
does not exist (a CI checkout) the gate SHALL accept the line on format and say that the block was
not measurable. A touched profile with neither line SHALL stay a finding.

#### Scenario: blocked line with a measured truncated tree passes

- **WHEN** a bot PR edits `agents/<profile>/` and the body carries `SYNC-BLOCKED: <profile> #2090 60/115 differ, 56 would SHRINK`
- **AND** the live profile home carries a larger copy of a differing file
- **THEN** `make check-pr-sync-line` exits 0 for that profile

#### Scenario: a blocked line the measurement does not support is fabrication

- **WHEN** the body carries `SYNC-BLOCKED: <profile> #<issue> <reason>` for a profile whose tree copy
  is NOT a truncated seed (no differing file has a larger live copy)
- **THEN** the gate reports a finding naming the profile and the fabrication

#### Scenario: no line at all still fails

- **WHEN** a bot PR edits `agents/<profile>/` and the body carries no `SYNC:` or `SYNC-BLOCKED:` line for it
- **THEN** the gate reports the #1724 finding naming the profile

#### Scenario: unmeasurable home accepts on format and says so

- **WHEN** the profile's live home does not exist (a CI checkout) and the body carries a format-valid
  `SYNC-BLOCKED:` line for a touched profile
- **THEN** the gate exits 0 and states the block was accepted unmeasured

### Requirement: bot-preflight prints the paste-ready blocked line it measured

`make bot-preflight` on the host SHALL print, for every touched profile whose tree copy is a
truncated seed, the exact line `SYNC-BLOCKED: <profile> #<issue> <measured file/byte reason>`
(the tracking issue named by `ISSUE=<n>`), and SHALL keep surfacing the `SYNC:` obligation for a
touched profile that is not truncated. A `SYNC-BLOCKED:` line in a prospective body that the host
measurement does not support SHALL be refused before push.

#### Scenario: truncated tree copy yields the blocked line

- **WHEN** the working diff touches `agents/<profile>/` whose live copy is larger than the tree copy
- **AND** `ISSUE=<n>` is supplied
- **THEN** `make bot-preflight` prints `SYNC-BLOCKED: <profile> #<n>` with the measured counts

#### Scenario: a fabricated blocked line is refused pre-push

- **WHEN** `BODY=<file>` carries `SYNC-BLOCKED:` for a profile whose tree copy is not truncated
- **THEN** the preflight refuses with a finding naming the profile
