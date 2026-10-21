# hermes-smoke-tool-call

## ADDED Requirements

### Requirement: The smoke proves a tool call, not a sentence

`make hermes-smoke` SHALL fail unless the run's own session transcript shows the agent calling its
**terminal** tool and the tool's result carrying a value that exists only in a file the harness wrote —
a value the prompt does not contain. A model that answers in text without a tool call SHALL fail the
smoke in seconds, and a missing transcript SHALL be a named failure, never a pass.

WHEN the smoke runs the alias the bots use and reads back the session it created
THEN it SHALL pass only when that session carries a `role='tool'`, `tool_name='terminal'` row whose
result contains `smoke-ok:<nonce>` AND the agent's final answer carries the same string, and SHALL
exit non-zero naming which of those was missing otherwise.

#### Scenario: a text-only answer fails the smoke

Given a session whose transcript carries an assistant answer and no tool call at all
When  the smoke evaluates that session
Then  it fails, naming that the model answered without calling a tool — the answer alone is not proof,
      because "ok" is exactly what a model with broken tool calling still returns.

- **Test:** `tests/test_hermes_smoke.py::test_a_text_only_transcript_is_a_failure`

#### Scenario: a terminal call that produced the nonce passes

Given a session whose transcript carries a `terminal` tool result containing `smoke-ok:<nonce>` and a
final answer carrying the same string
When  the smoke evaluates that session
Then  it reports no problem and exits zero.

- **Test:** `tests/test_hermes_smoke.py::test_a_terminal_call_carrying_the_nonce_passes`

#### Scenario: a tool that is not the terminal does not count

Given a session whose transcript carries a `write_file` tool result containing the nonce
When  the smoke evaluates that session
Then  it fails, naming the terminal tool as the one that had to run — the legs need shell access, and
      any other tool would let a model that cannot run commands pass.

- **Test:** `tests/test_hermes_smoke.py::test_a_non_terminal_tool_call_does_not_count`

#### Scenario: a tool count with no terminal result is not proof

Given a session whose `tool_call_count` is greater than zero but whose transcript carries no
`terminal` result containing the nonce
When  the smoke evaluates it
Then  it fails, so the summary counters alone can never stand in for the evidence.

- **Test:** `tests/test_hermes_smoke.py::test_a_tool_count_without_the_terminal_result_is_a_failure`

#### Scenario: a missing transcript is loud

Given a run that left no new session in `$HERMES_HOME/state.db`, or no database at all
When  the smoke evaluates it
Then  it fails with a message naming the transcript it could not read, instead of treating the absence
      of evidence as a pass.

- **Test:** `tests/test_hermes_smoke.py::test_a_missing_transcript_is_a_named_failure`

### Requirement: The prompt cannot be satisfied by echoing it

The smoke's prompt SHALL name the terminal tool and the exact command to run, and SHALL NOT contain
the value it asks for: the nonce is generated per run and written to a file whose path (not content)
appears in the prompt.

WHEN the prompt is built for a nonce
THEN it SHALL contain the token file's path, the command that prints it, and no occurrence of the
nonce itself.

#### Scenario: the nonce is not in the prompt

Given a freshly generated nonce and the prompt built for it
When  the prompt is inspected
Then  the nonce does not appear anywhere in it, while the token path and `printf 'smoke-ok:%s\n'` do —
      so only a real terminal call can produce the string the smoke asserts.

- **Test:** `tests/test_hermes_smoke.py::test_the_prompt_names_the_command_and_never_the_value`

### Requirement: The proof runs where the bots run, and cannot regress

`make _hermes-smoke` SHALL invoke `scripts/hermes_smoke.py run`, `issue-bot.yml`'s smoke step SHALL
still call `make hermes-smoke` before the long implementation step, and the text-echo prompt
(`Reply with exactly: ok`) SHALL appear nowhere in the repository.

WHEN the wiring is inspected
THEN the recipe, the workflow step and the absence of the old prompt SHALL all hold, so a future edit
cannot quietly turn the smoke back into a text assertion.

#### Scenario: the recipe and the workflow both run the real proof

Given the Makefile and `.github/workflows/issue-bot.yml`
When  the wiring test reads them
Then  `_hermes-smoke` runs `scripts/hermes_smoke.py run`, and the workflow's `Hermes routing smoke`
      step runs `make hermes-smoke`.

- **Test:** `tests/test_hermes_smoke.py::test_the_recipe_and_the_workflow_run_the_proof`

#### Scenario: the old text-echo prompt is gone

Given the repository's tracked files
When  they are searched for `Reply with exactly: ok`
Then  no file carries it, so the smoke cannot be reverted to a sentence assertion without going red.

- **Test:** `tests/test_hermes_smoke.py::test_the_text_echo_prompt_is_gone_from_the_tree`
