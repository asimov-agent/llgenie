# fix-engine-build-trigger-path-filter

## ADDED Requirements

### Requirement: the trigger discovers the producer by the API's real `.path` shape

`engine_build_trigger.py` MUST match GitHub's run-list `.path` field as the API returns it —
`.github/workflows/engine-build.yml` without a leading slash — in BOTH of its run-list filters:
`_existing_run_ids()` (the discovery/diff set) and `_push_group_holder()` (the stall-holder
probe). A `.path` filter that carries a leading slash (`/.github/…`) is a defect: it matches
nothing and makes the "find the JUST-dispatched producer and await its verdict" discipline dead
in production.

WHEN the trigger dispatches a `push=true` engine-build and reads back the run list
THEN it finds the new `workflow_dispatch` run by its real API path and awaits that run's verdict

#### Scenario: `_existing_run_ids` matches the producer by the real path

- **Given** the GitHub API returns `.path == ".github/workflows/engine-build.yml"` (no leading slash)
- **When** `_existing_run_ids` filters the run list for engine-build `workflow_dispatch` runs
- **Then** it returns the run ids (non-empty when an engine-build run exists), so the discovery
  loop can find the run it just dispatched
- **Test:** `tests/test_engine_build_trigger.py::test_the_mock_uses_the_real_api_path_shape` /
  the full suite exercises discovery via the re-shaped mock

#### Scenario: `_push_group_holder` matches by the real path

- **Given** an in-progress push=true engine-build run holding the concurrency group
- **When** `_push_group_holder` probes the run list
- **Then** it names that holder run (it is not invisible to the real path)
- **Test:** `tests/test_engine_build_trigger.py::test_stalled_behind_push_holder_is_named_not_a_bare_queued` (unchanged) exercising the re-shaped mock

### Requirement: a mis-shaped path filter is caught by the unit tests

The unit-test mock MUST model the GitHub API's real `.path` value (no leading slash), so that
reintroducing the leading slash in a source filter makes the discovery "new run not found" path
reachable in a test and the suite reds. A mock that hardcodes the wrong leading-slash string is
a shape-language lie and a regression the suite cannot see.

WHEN the source filter or the mock carries a leading-slash path
THEN the guard-by-test fails — the mock's path is the API's path, and a real dispatch under the
buggy filter can be demonstrated to red

#### Scenario: the mock path equals the real API path

- **Given** `tests/test_engine_build_trigger.py::_fake_gh` emits runs
- **When** it records each engine-build run's `.path`
- **Then** the value is `.github/workflows/engine-build.yml` (no leading slash)
- **Test:** `tests/test_engine_build_trigger.py::test_the_mock_uses_the_real_api_path_shape`
