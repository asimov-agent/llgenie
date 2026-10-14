# queued-run-alarm

## ADDED Requirements

### Requirement: Jobs queued far too long are reported, with their runner label

The alarm SHALL report every job of an in-progress run that is still `queued` after a
configurable threshold (default 30 minutes), naming its age, workflow, branch, run and the
**labels** it waits for, and SHALL explain that a queued job whose labels match no runner is
either an offline/unregistered self-hosted runner or exhausted hosted-runner minutes for that OS.

#### Scenario: a stuck macOS job is reported

- **GIVEN** a run whose `macos / unit` job has been queued for 95 minutes on `macos-15-intel`
- **WHEN** the alarm runs
- **THEN** the report SHALL name that job, its age and its label
- **AND** it SHALL say that no machine matches those labels

#### Scenario: a freshly queued job is not news

- **GIVEN** a job queued moments ago
- **WHEN** the alarm runs with the default threshold
- **THEN** it SHALL report nothing

#### Scenario: running and finished jobs are ignored

- **WHEN** the alarm inspects a job that is `in_progress` or `completed`
- **THEN** it SHALL not report it

### Requirement: A stuck queue makes the alarm red, once per run

The alarm SHALL exit 1 when it finds a stuck job (so a scheduled run fails visibly) and 0 when it
does not; a GitHub failure SHALL exit 2. With `--comment` it SHALL post at most one comment per
affected run, deduplicated against its own marker, so repeating the sweep cannot spam.

#### Scenario: the sweep goes red

- **WHEN** a stuck job exists
- **THEN** the exit code SHALL be 1

#### Scenario: commenting twice is a no-op

- **GIVEN** the alarm's own marker already on the run
- **WHEN** it runs again with `--comment`
- **THEN** it SHALL post nothing

#### Scenario: GitHub unreachable is loud

- **WHEN** the GitHub call fails
- **THEN** the exit code SHALL be 2 and the error SHALL be printed
