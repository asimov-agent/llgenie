# agent-profiles-live-comparison — spec delta

## ADDED Requirements

### Requirement: The live-root shape probe shall survive unreadable directories

The gate's profiles-directory probe SHALL treat every entry it cannot read — the base itself, a
candidate directory below it, or a candidate's `SOUL.md` — as not-a-profile and continue scanning.
The probe SHALL NOT abort the gate with an OSError; an unreadable shape is an answer ("this cannot
hold profiles"), not a crash.

#### Scenario: a typo whose parent is the filesystem root

- **WHEN** `HERMES_PROFILE_HOME=/nonexistent-home` (resolved base `/`, which contains unreadable
  system directories such as `/boot`)
- **THEN** the gate exits 0 with the audible skip caveat
- **AND** no "gate aborted" PermissionError line is printed and the tree checks still run

#### Scenario: an unreadable candidate inside a real profiles home

- **WHEN** one candidate directory under the base has mode 000 and another holds a `SOUL.md`
- **THEN** the comparison runs against the readable profiles, with no finding about the unreadable
  candidate masquerading as a verdict

### Requirement: A rejected resolved base shall be named in the skip line

When a **provided** profiles-home variable resolves to a directory that holds no
`<name>/SOUL.md`, the audible skip SHALL name the resolved base path so the reader can see which
directory was rejected. The no-variable default keeps its existing wording.

#### Scenario: provided variable, rejected base

- **WHEN** `HERMES_PROFILE_HOME` names a path whose parent exists but holds no profile directory
- **THEN** the skip line names that parent path and states the live rulebooks were NOT compared

### Requirement: The tightened probe shall not disable the comparison

A base that holds profiles SHALL still compare, still red `live-longer` when the tree is a prefix
of the live file, and the singular variable SHALL still resolve through its parent with the
"(its parent directory)" caveat.

#### Scenario: positive control

- **WHEN** the resolved base holds a profile whose live `SOUL.md` is longer than the tree's
- **THEN** the gate fails with the `live-longer` finding
