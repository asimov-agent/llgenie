# hermes-smoke-envelope-kind

## ADDED Requirements

### Requirement: the smoke names a lost or truncated tool-result envelope instead of an un-tracked empty success

`scripts/hermes_smoke.py::evaluate` SHALL classify each terminal tool-result body via an
`envelope_kind(body)` helper and name a body that never arrived (`lost`) or that is not a complete
parseable output envelope (`truncated`) as a distinct, channel-naming failure — never as an un-tracked
empty success. A well-formed envelope whose output is genuinely empty SHALL still read as an empty
command (success), not as suppression.

WHEN the smoke's transcript carries a `terminal` tool result whose body is empty/`None`
THEN the failure SHALL name the `terminal` channel and its lost envelope (`LOST`, `dropped`, or the
same signal), never a generic "no terminal result" without the cause.

WHEN the transcript carries a `terminal` tool result whose body is not a complete parseable envelope
THEN the failure SHALL name the channel and the truncation, never a clean empty read.

WHEN a well-formed envelope has genuinely empty output (e.g. `{"output": "", "exit_code": 0}`)
THEN it SHALL classify as `empty` (a real empty command), not as `lost` or `truncated`, and the
evaluated transcript SHALL NOT report suppression words (`lost`, `dropped`, `suppressed`,
`never arrived`) for it.

WHEN a real command's output is replayed as an empty success THEN the smoke SHALL NOT pass it as a
proven tool call — the empty suppression is detectable, never an untracked empty.

#### Scenario: a lost terminal envelope is named

Given a transcript whose `terminal` tool result body is empty (the envelope never arrived)
When  `evaluate` runs on it
Then  it fails naming the `terminal` channel and the lost envelope, not as an empty success.

- **Test:** `tests/test_hermes_smoke.py::test_a_lost_terminal_envelope_is_named_not_an_empty_success`

#### Scenario: a truncated terminal envelope is named

Given a transcript whose `terminal` tool result body is cut off mid-JSON
When  `evaluate` runs on it
Then  it fails naming the channel and the truncation, never as a clean empty.

- **Test:** `tests/test_hermes_smoke.py::test_a_truncated_terminal_envelope_is_named_not_an_empty_success`

#### Scenario: a genuinely empty result is the negative control

Given a well-formed envelope with genuinely empty output (`{"output": "", "exit_code": 0}`)
When  `envelope_kind` classifies it and `evaluate` runs over a matching transcript
Then  it classifies `empty`, is NOT in `{lost, truncated}`, and the evaluate problems never use the
      suppression vocabulary.

- **Test:** `tests/test_hermes_smoke.py::test_a_genuinely_empty_result_is_not_reported_as_suppression`

#### Scenario: real output replayed as empty is detected

Given a transcript that would prove a tool call with real output but whose terminal result is an empty
success (the channel dropped the bytes)
When  `evaluate` runs on it
Then  it does not pass as a proven tool call and names the terminal channel.

- **Test:** `tests/test_hermes_smoke.py::test_forcing_a_real_command_output_to_empty_success_is_detected`
