# secret-output-rules — spec delta

Capability: `secret-output-rules`
Issue: [#361](https://github.com/asimov-agent/llgenie/issues/361)

## ADDED Requirements

### Requirement: GitHub's own token is a secret in a `run:` block

`check_secret_output` SHALL report `secrets-in-run-block` when `${{ github.token }}`,
`${{ github['token'] }}` or `${{ github["token"] }}` is interpolated inside a workflow's `run:` block,
and SHALL NOT report the same expression when it is passed through `env:`.

WHEN a workflow interpolates GitHub's own token into a `run:` block,
THEN the guard SHALL name the rule and the line, because the token becomes script text, `ps` and
`--debug` output exactly like `secrets.GITHUB_TOKEN`.

#### Scenario: github.token in a run block fails
Given a workflow whose `run:` block contains `${{ github.token }}`,
When   the guard scans it,
Then   it reports `secrets-in-run-block` for that line.
- **Test:** `tests/test_secret_output.py::test_github_token_in_a_run_block_is_a_violation`

#### Scenario: the bracketed spelling fails the same way
Given a workflow whose `run:` block contains `${{ github['token'] }}`,
When   the guard scans it,
Then   it reports `secrets-in-run-block` for that line.
- **Test:** `tests/test_secret_output.py::test_bracketed_github_token_in_a_run_block_is_a_violation`

#### Scenario: env: is the correct form
Given a workflow that passes `${{ github.token }}` through an `env:` entry,
When   the guard scans it,
Then   it reports nothing.
- **Test:** `tests/test_secret_output.py::test_github_token_passed_through_env_is_not_a_violation`

### Requirement: a whole stdout into `$GITHUB_OUTPUT` is a violation

`check_secret_output` SHALL report `whole-stdout-into-output-file` when a single pipe (or a `$(…)`
substitution) feeds `$GITHUB_OUTPUT`, and SHALL NOT report the safe shape where the pipe sits inside a
quoted argument (`echo "k=$(cmd | …)" >> "$GITHUB_OUTPUT"`), nor a shell `a || b` chain that ends in
that redirect.

WHEN a workflow redirects a command's whole stdout into the output file,
THEN the guard SHALL fail, because the file must hold `key=value` only.

#### Scenario: a pipeline into the output file fails
Given a workflow whose `run:` block is `make plan | python3 … >> "$GITHUB_OUTPUT"`,
When   the guard scans it,
Then   it reports `whole-stdout-into-output-file`.
- **Test:** `tests/test_secret_output.py::test_a_pipeline_into_github_output_is_a_violation`

#### Scenario: a substitution into the output file fails
Given a workflow whose `run:` block is `$(make plan) >> "$GITHUB_OUTPUT"`,
When   the guard scans it,
Then   it reports `whole-stdout-into-output-file`.
- **Test:** `tests/test_secret_output.py::test_a_substitution_into_github_output_is_a_violation`

#### Scenario: the quoted computed form stays green
Given a workflow whose `run:` block is `echo "matrix=$(make plan | …)" >> "$GITHUB_OUTPUT"`,
When   the guard scans it,
Then   it reports nothing.
- **Test:** `tests/test_secret_output.py::test_a_quoted_computed_key_value_is_not_a_violation`

### Requirement: a whole stdout into the job log is a violation

`check_secret_output` SHALL report `whole-stdout-into-log` for `… | tee /dev/stderr` (or
`/dev/stdout`), and SHALL NOT report `tee <file>`, which is a file and not the job log.

WHEN a command's whole stream is copied into the job log,
THEN the guard SHALL fail, because GitHub masks registered values only.

#### Scenario: tee into the job log fails
Given a script whose line pipes a command into `tee /dev/stderr`,
When   the guard scans it,
Then   it reports `whole-stdout-into-log`.
- **Test:** `tests/test_secret_output.py::test_tee_into_the_job_log_is_a_violation`

#### Scenario: tee into a file is allowed
Given a script whose line pipes a command into `tee /tmp/out.log`,
When   the guard scans it,
Then   it reports nothing.
- **Test:** `tests/test_secret_output.py::test_tee_into_a_file_is_not_a_violation`

### Requirement: the tree stays green under the new rules

The three rules SHALL NOT flag the repository as it stands: every existing `${{ github.token }}` use
sits in `env:` and every existing `>> "$GITHUB_OUTPUT"` writer is the quoted computed form.

WHEN the guard runs over this repository,
THEN it SHALL report no violation, and `make check-secret-output` SHALL exit zero.

#### Scenario: the repository is clean
Given the tracked tree,
When   `python3 scripts/check_secret_output.py check` runs,
Then   it exits zero with no violation.
- **Test:** `tests/test_secret_output.py::test_this_repository_never_prints_a_secret_value`
