# refiner-pick-reliability

## ADDED Requirements

### Requirement: the thread read issues only `gh`-valid argv

`_thread()` SHALL NOT combine `--comments` with `--json` (the CLI refuses that pair); the comment
bodies SHALL be requested through the `comments` JSON field alone.

#### Scenario: the pick does not combine --comments with --json

- **GIVEN** a `gh` that refuses `--comments` together with `--json` on `issue view` (as the real CLI
  does),
- **WHEN** the refiner reads an issue's thread,
- **THEN** the call succeeds and requests `comments` through `--json`.

- **Test:** `tests/test_issue_refiner.py::test_the_thread_read_never_combines_comments_with_json`

### Requirement: a failed pick is loud, never a green no-op

`issue-refiner.yml`'s pick step SHALL fail the run when `make issue-refiner-pick` exits non-zero.

#### Scenario: a non-zero pick fails the step

- **GIVEN** the pick step's `run:` block,
- **WHEN** it is read,
- **THEN** it captures the pick's exit code and exits non-zero when it is not 0.

- **Test:** `tests/test_issue_refiner.py::test_the_pick_step_fails_loudly_when_the_pick_fails`
