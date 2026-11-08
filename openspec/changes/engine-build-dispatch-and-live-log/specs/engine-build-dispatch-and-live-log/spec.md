# engine-build-dispatch-and-live-log

## ADDED Requirements

### Requirement: A detached checkout never dispatches at the literal `HEAD`

The trigger SHALL resolve its dispatch ref from an explicit `--branch`, then `GITHUB_HEAD_REF`, then
the checkout's own branch, and SHALL refuse with a message naming the inputs when none of them names
a ref. It SHALL NOT pass the literal `HEAD` to `gh workflow run --ref`.

WHEN a `pull_request` checkout has no explicit `--branch`
THEN the dispatch uses `GITHUB_HEAD_REF` and the dispatched run's own id is awaited and recorded.

#### Scenario: a detached pull_request checkout dispatches at the source branch

Given a detached checkout whose `git rev-parse --abbrev-ref HEAD` answers `HEAD`
And `GITHUB_HEAD_REF` names the PR's head branch
When  `check()` dispatches for a repinned engine
Then  the dispatch argv carries `--ref <head branch>`, never `HEAD`, and the new run's id is reported.

- **Test:** `tests/test_engine_build_trigger.py::test_a_detached_pull_request_checkout_dispatches_at_the_head_ref`

#### Scenario: a checkout that names no ref refuses instead of dispatching

Given a detached checkout with `GITHUB_HEAD_REF` unset and no explicit `--branch`
When  `check()` is asked to dispatch
Then  it dispatches nothing, exits non-zero, and its message names both `--branch` and `GITHUB_HEAD_REF`.

- **Test:** `tests/test_engine_build_trigger.py::test_a_detached_checkout_that_names_no_ref_refuses_instead_of_dispatching`

### Requirement: Every workflow input is its own `--field`

`gh workflow run` SHALL receive one `--field <k=v>` per input, so no input is passed as a positional
argument.

WHEN the dispatch argv is built for any combination of `engine`, `push` and `arch`
THEN each input follows its own `--field` and no `k=v` token is left positional.

#### Scenario: three inputs produce three `--field` pairs

Given a dispatch for one engine, `push=true` and an arch
When  the argv is built
Then  it carries exactly three `--field` pairs: `engine=…`, `push=true`, `arch=…`.

- **Test:** `tests/test_engine_build_trigger.py::test_every_dispatch_input_gets_its_own_field_argument`

### Requirement: A rejected dispatch reports the CLI's own reason

A non-zero `gh workflow run` SHALL be concluded as a dispatch failure whose message contains the
CLI's error text, instead of awaiting a run that does not exist and reporting an empty run id.

WHEN the dispatch command exits non-zero
THEN the trigger exits non-zero and its message contains the CLI's error text.

#### Scenario: an HTTP 422 refusal is printed, not swallowed

Given a dispatch the CLI rejects with an HTTP 422 and its reason
When  the trigger runs
Then  the run is concluded `dispatch-failed` and the failure line carries the CLI's error text.

- **Test:** `tests/test_engine_build_trigger.py::test_a_rejected_dispatch_reports_the_cli_reason_not_a_bare_failure`

### Requirement: `proc.run_live` streams both child streams through

`scripts/proc.py` SHALL expose a `run_live` policy that inherits the caller's descriptors for both
streams and returns the child's exit code without raising on a non-zero exit.

WHEN a child writes to stdout or stderr while it runs
THEN the bytes reach the caller's own stdout/stderr as they are written, and `returncode` is returned.

#### Scenario: a child's line is readable before the child exits

Given a child that prints one line and then sleeps
When  `run_live` runs it
Then  the caller reads the line while the child is still running.

- **Test:** `tests/test_proc.py::test_run_live_a_line_reaches_the_caller_before_the_child_exits`

#### Scenario: the exit code is still the caller's verdict

Given a child that exits 7
When  `run_live` runs it
Then  it returns `returncode == 7` and raises nothing.

- **Test:** `tests/test_proc.py::test_run_live_returns_the_child_exit_code_and_never_raises`

### Requirement: The long engine-image build step is streamed, not captured

`scripts/engine_image.py` SHALL run both `buildx build` steps (the `--push` build and the local
build) through `run_live`, keeping `_sh` for short commands whose output is re-surfaced.

WHEN `_buildx` runs a build
THEN the build command reaches `run_live`, and its exit code is still the caller's verdict.

#### Scenario: a local build streams and keeps its rc

Given a local (non-push) build
When  `_buildx` runs
Then  the build command runs through `run_live` with `--progress=plain` and `--load`.

- **Test:** `tests/test_engine_image_matrix.py::test_a_local_build_streams_its_log_through_run_live`

#### Scenario: a failing push build reds the cell

Given a push build whose child exits 2
When  `_buildx` runs
Then  it returns 2 and the command ran through `run_live`.

- **Test:** `tests/test_engine_image_matrix.py::test_a_push_build_streams_its_log_and_keeps_the_exit_code`
