# live-snapshot-compare

## ADDED Requirements

### Requirement: each comparison run snapshots the live files it compares

`scripts/check_agent_profiles.py` MUST read every compared live counterpart exactly once before the
tree/live walk and record, per file, the snapshot's size, mtime and a sha256 content digest. All
live-side comparisons — the size compare behind `live-longer`, the line-set compares, the
live-only-file reports — MUST consume that snapshot instead of re-touching the live path, so a file
rewritten mid-run cannot change a finding after the run measured it.

#### Scenario: a file mutated after the snapshot still renders the snapshot bytes

- **Given** a fixture live file snapshotted by a run
- **When** the file is rewritten before the finding is rendered
- **Then** the finding reports the snapshot's size and digest, not the mutated file
- **Test:** `tests/test_agent_profiles.py::test_live_file_mutated_after_snapshot_still_renders_the_snapshot`

#### Scenario: exit-code semantics are untouched

- **Given** the existing red-1 / green-0 fixture pins
- **When** the snapshot pass is active
- **Then** every existing finding key and exit code is unchanged
- **Test:** the unchanged green run of `tests/test_agent_profiles.py`

### Requirement: findings and the OK line name the snapshot they were measured from

Each live-side finding detail MUST carry `live snapshot <sha12>` (the snapshot content digest) beside
the existing size/mtime stamp, and the OK comparison line MUST name the snapshot manifest (file
count and manifest digest), so a reader can identify the exact bytes a run saw.

#### Scenario: a live-longer finding is re-checkable against its snapshot

- **Given** a `FAIL live-longer` finding rendered from a snapshot
- **When** a reader compares the finding's snapshot digest against the live tree
- **Then** the digest identifies the exact live bytes the run compared
- **Test:** `tests/test_agent_profiles.py::test_live_longer_names_its_snapshot_digest` plus the OK-line pin
