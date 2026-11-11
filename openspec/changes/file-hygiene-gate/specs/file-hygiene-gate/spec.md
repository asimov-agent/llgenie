# file-hygiene-gate

## ADDED Requirements

### Requirement: `.gitignore` is categorical about logs and dot-scratch artifacts

`.gitignore` MUST carry a blanket `*.log` rule (the existing per-name rules stay for readability)
and a rule for dot-prefixed run-artifact names `.<word><digits>.<ext>` — a leading dot, letters/digits
with at least one digit before the extension dot (e.g. `.pr874.md`, `.unit2.log`) — so a new log name
is ignored without being enumerated. An arbitrary new `*.log` MUST be ignored by `git check-ignore`,
while a valued hidden file with no digits (`.env.example`) MUST stay trackable.

WHEN git is asked whether a new `.foo.log` and a valued hidden `.env.example` are ignored
THEN `.foo.log` is ignored by a blanket rule and `.env.example` is not, so the rule is narrow, not a
catch-all dot blacklist.

#### Scenario: a new `.foo.log` is ignored by the blanket rule

- **Given** the repository's `.gitignore` with the blanket `*.log` rule
- **When** git is asked whether a `.foo.log` that no per-name rule enumerates is ignored
- **Then** it is ignored, so a new log name cannot become committable without an ignore edit
- **Test:** `tests/test_file_hygiene.py::test_bare_a_dot_foo_log_is_ignored_by_real_git`

#### Scenario: a valued hidden file without digits stays trackable

- **Given** the blanket `*.log` + dot-scratch rules
- **When** git is asked whether `.env.example` (a documented template, no digits) is ignored
- **Then** it is NOT ignored — a valued hidden file is not caught by accident
- **Test:** `tests/test_file_hygiene.py::test_bare_a_valued_hidden_file_stays_trackable`

### Requirement: the two measured stray artifacts are removed forward-only

`.unit2.log` and `.pr874.md` MUST NOT be tracked any more (a forward `git rm`); history is not
rewritten.

WHEN the tree's tracked files are listed
THEN neither `.unit2.log` nor `.pr874.md` appears, and no past commit is rewritten.

#### Scenario: the named artifacts are gone from the tracked tree

- **Given** the issue measured `.unit2.log` and `.pr874.md` as tracked on `main`
- **When** the current tree's tracked files are listed
- **Then** neither stray artifact is tracked any more
- **Test:** `tests/test_file_hygiene.py::test_bare_the_named_artifacts_are_not_tracked`

### Requirement: the gate refuses a committed runtime artifact

The gate MUST scan every file git tracks and fail, naming the path only, when a file matches a
`*.log` or a dot-prefixed `.<word><digits>.<ext>` scratch shape. A clean tree MUST pass, and an
untracked (ignored) `.log` MUST NOT be a finding — the gate reads tracked files.

WHEN the tracked tree contains a `*.log` or a dot-scratch artifact
THEN the gate reports that path (and no other and no file contents) and is red; a tree with neither
shape passes.

#### Scenario: a planted tracked `*.log` goes the gate red

- **Given** a repository whose tracked tree includes a `run.log` and an empty exception fixture
- **When** the gate scans the tracked files
- **Then** it reports exactly `run.log` (a planted violation goes red)
- **Test:** `tests/test_file_hygiene.py::test_a_tracked_log_is_refused`

#### Scenario: a planted dot-scratch name goes the gate red

- **Given** a repository whose tracked tree includes a `.pr874.md` scratch artifact
- **When** the gate scans the tracked files
- **Then** it reports exactly `.pr874.md`
- **Test:** `tests/test_file_hygiene.py::test_a_tracked_dot_scratch_is_refused`

#### Scenario: a clean tree passes

- **Given** a repository whose tracked files match neither artifact shape
- **When** the gate scans the tracked files
- **Then** it reports no artifact or stale-exception finding
- **Test:** `tests/test_file_hygiene.py::test_a_clean_tree_passes`

#### Scenario: an untracked ignored log is not a finding

- **Given** a repository where a `.foo.log` is written but never committed
- **When** the gate scans the tracked files
- **Then** the uncommitted log does not appear (the `.gitignore` blanket rule already keeps it out)
- **Test:** `tests/test_file_hygiene.py::test_an_untracked_ignored_log_is_not_a_finding`

### Requirement: the allowlist is dated, honoured, and cannot rot

An intentional tracked file that matches a pattern MUST be allowed only when it is recorded in the
dated exception fixture (`tests/fixtures/file-hygiene-exceptions.json`) with a reason, a date and an
issue. A recorded exception MUST be honoured; an exception whose file is no longer tracked or no
longer matches a pattern MUST fail as STALE.

WHEN the gate reads the exceptions fixture
THEN a recorded exception is honoured, and an entry that names no current artifact (or a malformed
fixture) is a finding.

#### Scenario: a dated exception honours an intentional file

- **Given** a tracked fixture log and an exception fixture entry naming it with a reason, a date and
  an issue
- **When** the gate scans the tracked tree with that fixture loaded
- **Then** the recorded exception is honoured and the gate passes
- **Test:** `tests/test_file_hygiene.py::test_a_dated_exception_honors_an_intentional_file`

#### Scenario: a stale exception fails

- **Given** an exception fixture entry naming a file that no longer exists in the tree
- **When** the gate scans the tracked tree against that fixture
- **Then** the expired exception is a stale-exception finding and the gate is red
- **Test:** `tests/test_file_hygiene.py::test_a_stale_exception_fails`

### Requirement: the gate is wired into the unit lane and lane-preflight

`make check-file-hygiene` MUST exist with a `##` help line, MUST be declared `.PHONY:` (it produces
no file of its name), MUST run the script, MUST be a step of the unit lane (`ci-unit`), and MUST be a
`FAST_GATES` member so `make lane-preflight` (and the issue-bot's pre-push gate) reach it.

WHEN the Makefile and `scripts/issue_bot_gates.py` are read
THEN `check-file-hygiene` is a phony `##` target that runs the script and is a step of `ci-unit` and
a `FAST_GATES` member.

#### Scenario: ci-unit runs the hygiene gate

- **Given** the `ci-unit` recipe and the `check-file-hygiene` recipe
- **When** their steps are read
- **Then** `ci-unit` runs `make check-file-hygiene` and the gate runs `scripts/check_file_hygiene.py
  check` (not a no-op)
- **Test:** `tests/test_file_hygiene.py::test_ci_unit_runs_the_hygiene_gate`

#### Scenario: lane-preflight reaches the hygiene gate

- **Given** the one `FAST_GATES` tuple the issue-bot and lane-preflight both import
- **When** its members are read
- **Then** `check-file-hygiene` is a fast gate, so `make lane-preflight` reaches it
- **Test:** `tests/test_file_hygiene.py::test_lane_preflight_reaches_the_hygiene_gate`

#### Scenario: the gate is declared phony

- **Given** the `.PHONY:` declaration and its line continuations
- **When** its members are read
- **Then** `check-file-hygiene` is declared `.PHONY:`, so `make` cannot run nothing while reporting
  green
- **Test:** `tests/test_file_hygiene.py::test_check_file_hygiene_is_declared_phony`
