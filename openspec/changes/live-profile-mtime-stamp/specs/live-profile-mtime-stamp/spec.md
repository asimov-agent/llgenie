## ADDED Requirements

### Requirement: A live-comparison finding names the file state it measured
Every live-comparison finding (`live-longer`, `live-lines-missing`) SHALL name the compared live
file's size in bytes, its mtime as a UTC ISO stamp, and the check's own run-start timestamp
alongside the tree/live byte counts, so a reader can tell whether the finding is stale before
acting on it.

#### Scenario: a live-longer finding is datable
- **WHEN** a live rulebook is longer than its tree copy and the gate reports `live-longer`
- **THEN** the finding names the live size, the live mtime in UTC ISO form, and the run's start stamp

#### Scenario: a live-lines-missing finding is datable
- **WHEN** a tree copy lacks lines the live profile carries and the gate reports `live-lines-missing`
- **THEN** the finding names the live byte count, the live mtime in UTC ISO form, and the run's start stamp

### Requirement: The OK comparison line carries the same stamp
When the live comparison ran and found nothing, the OK line SHALL state how many live/tree file
pairs were compared, the min..max live mtimes seen during the comparison, and the run's start
stamp — so green and red runs are equally datable. When comparison was skipped, the existing
audible SKIPPED line SHALL remain the explicit note.

#### Scenario: green is as datable as red
- **WHEN** `check-agent-profiles` exits 0 after comparing live profiles
- **THEN** the OK line names the compared file-pair count, the live mtime range, and the run-start stamp

#### Scenario: skill-parity green is datable too
- **WHEN** `skill_parity.py` prints its OK line after comparing mirrored skill surfaces
- **THEN** the OK line names the compared file count, the newest live mtime, and the run-start stamp

### Requirement: Stamping never changes a verdict
The stamp SHALL be message text only; the exit codes of `make check-agent-profiles` and
`make profile-drift` SHALL be unchanged by the stamping.

#### Scenario: exit codes survive the stamp
- **WHEN** a fixture host produces a red live-comparison finding and a clean mirror produces 0
- **THEN** the red fixture exits 1 and the clean fixture exits 0, exactly as before the stamp
