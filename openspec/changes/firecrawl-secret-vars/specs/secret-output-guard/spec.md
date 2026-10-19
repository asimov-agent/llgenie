# secret-output-guard

## ADDED Requirements

### Requirement: Every credential the agent receives is scanned and redacted by name

`scripts/check_secret_output.py::SECRET_VARS` SHALL contain every variable named by the Makefile's
`AGENT_SHELL_KEYS` (the credential list forwarded into the agent image) in addition to every name a
workflow reads as `secrets.<NAME>`. The static guard and `scripts/scrub_log.py` SHALL both read this
one list, so a key added to the forwarding seam cannot be invisible to either.

WHEN a variable is named in `AGENT_SHELL_KEYS`
THEN `SECRET_VARS` contains it, `make check-secret-output` scans a printed value of it, and
`scripts/scrub_log.py::redact` replaces its value in the transcript.

#### Scenario: the Firecrawl key is in the one list

Given the Makefile's `AGENT_SHELL_KEYS` names `FIRECRAWL_API_KEY`,
When  the static guard's credential list is read,
Then  `FIRECRAWL_API_KEY` is a member of `SECRET_VARS`.

- **Test:** `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets`

#### Scenario: a printed Firecrawl value is a finding

Given a worksheet line that prints `$FIRECRAWL_API_KEY`,
When  `make check-secret-output` scans it,
Then  the guard reports a finding naming the file and rule instead of passing.

- **Test:** `tests/test_secret_output.py::test_a_printed_firecrawl_value_is_a_finding`

#### Scenario: the redactor masks every spelling of the Firecrawl value

Given `FIRECRAWL_API_KEY` holds a value in the redactor's environment,
When  the value appears raw, URL-encoded or base64-encoded in the captured stream,
Then  `redact` replaces every spelling with `***` and reports a non-zero redaction count.

- **Test:** `tests/test_scrub_log.py::test_redacts_the_firecrawl_value_in_every_spelling`

#### Scenario: a forwarded key missing from the list is a red test

Given a variable added to `AGENT_SHELL_KEYS` but not to `SECRET_VARS`,
When  `make test-unit` runs the roster test,
Then  it fails naming the variable.

- **Test:** `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets`
