# agent-log-redaction — spec delta

Capability: `agent-log-redaction`
Issue: [#359](https://github.com/asimov-agent/llgenie/issues/359)

## ADDED Requirements

### Requirement: every public agent leg redacts its stream

Every make target that starts the agent image SHALL run its command through ONE macro,
`$(call scrubbed_run,…)`, which captures the stream to `$(HERMES_LOG)`, prints only the redactor's
bounded tail, writes the REDACTED whole log to `$(HERMES_LOG_SCRUBBED)`, and preserves the command's
own exit status.

WHEN an agent leg runs,
THEN its console output SHALL be the redactor's bounded tail of the REDACTED stream, and a non-zero
command SHALL leave the leg non-zero.

#### Scenario: the seam redacts and keeps the exit status
Given a command that prints a sentinel value and exits non-zero,
When   it runs through `$(call scrubbed_run,…)` in the real Makefile,
Then   the sentinel appears nowhere in the console, the REDACTED file holds `***` for it, and make
       reports the command's own `Error N` so a red run stays red.
- **Test:** `tests/test_scrub_log.py::test_the_macro_redacts_the_stream_and_keeps_the_exit_status`

#### Scenario: no leg prints raw
Given every make target whose recipe names `$(AGENT_IMAGE)`,
When   the suite inspects the Makefile,
Then   each goes through `$(call scrubbed_run,` and a leg that does not is a failure.
- **Test:** `tests/test_scrub_log.py::test_every_public_agent_leg_goes_through_the_macro`

### Requirement: the redactor masks every spelling of every value, and the shapes

`scripts/scrub_log.py` SHALL read the secret values BY NAME from its environment — the name list
lives once, in `scripts/check_secret_output.py::SECRET_VARS` — and replace the raw value, its
URL-encoded form, its URL-plus-encoded form and its base64 forms, plus credential SHAPES
(`ghp_…`, `github_pat_…`, `hf_…`, `sk-…`, `ev_…`, `Bearer …`) that never entered its environment. It
SHALL print a redaction COUNT and the redacted lines, and SHALL never print a value, a prefix or a
slice. A value shorter than the minimum length SHALL be left alone (replacing it would shred the log
without hiding anything).

WHEN a captured log holds a value in any spelling,
THEN every spelling SHALL be replaced by the mask, the variable NAME and the prose SHALL survive, and
the printed output SHALL carry a count.

#### Scenario: all spellings and shapes are masked, prose and names survive
Given a log holding a sentinel value raw, URL-encoded and base64, plus a credential shape,
When   the redactor runs with that value in its environment by name,
Then   no spelling and no shape survives, `NOUS_API_KEY` and the surrounding lines do, and a count is
       returned.
- **Test:** `tests/test_scrub_log.py::test_every_spelling_of_a_value_is_redacted`

#### Scenario: a short value does not shred the log
Given a value shorter than the minimum length,
When   the redactor runs,
Then   the text is unchanged and the count is zero.
- **Test:** `tests/test_scrub_log.py::test_a_short_value_is_left_alone`

#### Scenario: only a bounded tail is printed
Given a captured log longer than the requested tail,
When   the redactor prints,
Then   only that many `[agent]` lines appear, the rest is announced as omitted with the artifact path,
       and no value appears anywhere in the output.
- **Test:** `tests/test_scrub_log.py::test_the_cli_prints_only_a_bounded_tail`

### Requirement: a stream that cannot be read is loud

`scripts/scrub_log.py` SHALL exit 2 with a reason when the captured log does not exist, so a missing
transcript never reads as a clean run.

WHEN the captured log is absent,
THEN the redactor SHALL fail loudly instead of printing an empty transcript.

#### Scenario: missing input fails closed
Given no captured log,
When   the redactor runs on that path,
Then   it exits 2 and says the log could not be read.
- **Test:** `tests/test_scrub_log.py::test_a_missing_log_is_loud`

### Requirement: only the REDACTED transcript is published

A bot workflow SHALL upload `$(HERMES_LOG_SCRUBBED)` as its transcript artifact and SHALL NOT upload
the raw `$(HERMES_LOG)` — the raw file holds the unredacted stream by construction.

WHEN a bot job finishes,
THEN the run carries the REDACTED transcript, named for what it is, and no step uploads the raw log.

#### Scenario: the bot jobs publish the redacted file only
Given `.github/workflows/{fix-bot,issue-bot,issue-refiner,rebase-bot}.yml`,
When   the suite reads each file,
Then   each uploads `hermes-run.scrubbed.log` under a name that says "redacted", and no `path:` names
       the raw `hermes-run.log`.
- **Test:** `tests/test_scrub_log.py::test_the_workflows_publish_only_the_redacted_log`
