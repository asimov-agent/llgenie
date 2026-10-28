# jev-preflight

## ADDED Requirements

### Requirement: a bot job's JEV preflight receives the provider key it requires

A bot job whose step runs the JEV preflight with `NERVE_REQUIRE=1` MUST provide `TYPESAFE_API_KEY` to
that step, because the leg's guard refuses to start without it. The issue-dedupe sweep's `dedup` job
MUST carry the key from the repository secret, and its preflight step MUST run the target that reports a
failure, never the bare target.

WHEN the dedup job reaches its preflight step THEN the provider key is in the step's environment and the
step runs `make jev-preflight-required`.

#### Scenario: the dedupe job passes the key the preflight requires

- **Given** the `issue-dedupe` workflow's `dedup` job
- **When**   its preflight step is read
- **Then**   the job's env carries `TYPESAFE_API_KEY` from `secrets.TYPESAFE_API_KEY`, and the step runs
  `make jev-preflight-required` with `GH_TOKEN` and the run URL
- **Test:** `tests/test_jev_preflight_tracker.py::test_the_dedupe_job_passes_the_key_the_preflight_requires`

#### Scenario: the dedupe leg's container receives the provider key, as the refiner's does

- **Given** the `issue-dedup` make recipe that starts the agent image
- **When**   its `docker run` forwarding is read
- **Then**   it forwards `-e TYPESAFE_API_KEY` to the image, because the job-level secret reaches only
  the host step, not the decision leg's container
- **Test:** `tests/test_jev_preflight_tracker.py::test_the_dedupe_leg_receives_the_provider_key_like_the_refiner_does`

### Requirement: a preflight failure names its class and its fix

When the JEV preflight fails, the run MUST say which failure class it is — read from the preflight's own
output, never guessed — print the measured line, and print the fix an operator can act on. The step
MUST stay red: the report explains the failure, it does not soften it.

WHEN the preflight fails THEN the output names the class, the measured line and that class's fix.

#### Scenario: the measured missing-key failure is its own class with its fix

- **Given** the exact output of issue-dedupe runs 40697636784 / 40702295009
- **When**   the tracker classifies it
- **Then**   the class is `key-missing`, the measured line is carried, and the fix names
  `TYPESAFE_API_KEY` and where it has to be passed
- **Test:** `tests/test_jev_preflight_tracker.py::test_the_missing_provider_key_is_its_own_class_and_names_the_fix`

#### Scenario: every preflight failure the script can print is a known class

- **Given** one output per failure the preflight can report
- **When**   each is classified
- **Then**   the class is the preflight's own vocabulary and an unrecognised failure is `unknown`
- **Test:** `tests/test_jev_preflight_tracker.py::test_each_failure_class_is_read_from_the_preflights_own_words`

### Requirement: one tracker issue per failure class

A preflight failure MUST have exactly one open tracker issue per class. The first failure of a class
files one issue in the repository's issue shape, labelled `agent:implement`, whose first line is the
marker; a later failure of the same class MUST file nothing and point at the existing issue.

WHEN a class fails for the first time THEN one issue is filed; WHEN it fails again THEN no second issue
exists.

#### Scenario: the first failure files one tracker in the issue shape

- **Given** a repository with no open tracker for the class
- **When**   the tracker reports a failure with the run URL
- **Then**   exactly one issue is created, its first line is `<!-- jev-preflight: key-missing -->`, its
  headings are the repository's six sections in order, and it carries the run and the measured line
- **Test:** `tests/test_jev_preflight_tracker.py::test_the_first_failure_files_one_tracker_in_the_issue_shape`

#### Scenario: a second failure of the same class files nothing

- **Given** an open tracker for `key-missing`
- **When**   a later run fails the same way
- **Then**   no second issue is created and the tracker exits clean
- **Test:** `tests/test_jev_preflight_tracker.py::test_a_second_run_of_the_same_class_files_nothing`

#### Scenario: two classes are two trackers

- **Given** a `key-missing` tracker already filed
- **When**   the preflight later fails as `plugin-missing`
- **Then**   that class gets its own issue, so one fix is not read as the other's
- **Test:** `tests/test_jev_preflight_tracker.py::test_two_classes_are_two_trackers`

### Requirement: a local run never writes to the repository

Only the CI step files a tracker. A person running `make jev-preflight-required` on their own host MUST
get the class and the fix and NO repository write, because a host-local precondition (a missing Docker
daemon, a stale image) is not a repository failure. Measured 2026-10-28: a local run on a Docker-less
host filed a real `unknown` tracker (#809).

WHEN the target runs outside CI THEN the tracker prints the class and the fix and makes no `gh` call.

#### Scenario: a local run reports and writes nothing

- **Given** a host whose preflight cannot start (no Docker daemon)
- **When**   the tracker reports with `--local`
- **Then**   it prints the class and the fix, calls `gh` zero times, and the repository is untouched
- **Test:** `tests/test_jev_preflight_tracker.py::test_a_local_run_reports_and_writes_nothing`

### Requirement: a tracker that cannot report is loud

A tracker invoked with no repository, or whose `gh` write fails, MUST return non-zero and say why on the
run's output — never pass silently, and never replace the preflight's own red with a green tracker.

WHEN the tracker cannot file THEN it exits non-zero with the reason on stderr.

#### Scenario: an unset repository files nothing and says so

- **Given** a tracker invoked without `REPO`
- **When**   it reports a failure
- **Then**   it returns non-zero and attempts no `gh` call
- **Test:** `tests/test_jev_preflight_tracker.py::test_an_unset_repo_is_loud_and_files_nothing`

#### Scenario: a refused gh write is reported, not swallowed

- **Given** a `gh` that refuses the write
- **When**   the tracker reports
- **Then**   it returns non-zero with the reason on stderr
- **Test:** `tests/test_jev_preflight_tracker.py::test_a_gh_failure_is_reported_not_swallowed`
