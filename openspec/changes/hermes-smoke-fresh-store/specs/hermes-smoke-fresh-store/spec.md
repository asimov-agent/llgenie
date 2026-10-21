# hermes-smoke-fresh-store

## ADDED Requirements

### Requirement: the smoke runs first and judges the store it created

`scripts/hermes_smoke.py run` MUST invoke Hermes before requiring a transcript store. A `HERMES_HOME`
whose `state.db` does not exist yet MUST NOT stop the run — that store is what a successful run
creates. After the call, the smoke MUST fail loudly, naming the path, when no store exists; MUST fail
naming the reason when the store exists but cannot be read as a sessions store; and MUST fail naming
the missing session when the store holds no new session.

WHEN a run starts against a fresh `HERMES_HOME`
THEN Hermes is invoked, and only the store the run leaves behind is judged.

#### Scenario: a fresh home with no store passes when the session proves the call

- **Given** a `HERMES_HOME` with no `state.db`, and a `hermes` that writes a session whose `terminal`
  tool result and final answer carry `smoke-ok:<nonce>`
- **When** the smoke runs
- **Then** it exits 0 and reports the session that proved the tool call
- **Test:** `tests/test_hermes_smoke.py::test_a_fresh_home_with_no_store_passes_when_the_session_proves_the_call`

#### Scenario: a run that writes no store is a named failure

- **Given** a `HERMES_HOME` with no `state.db`, and a `hermes` that exits 0 and writes nothing
- **When** the smoke runs
- **Then** it exits non-zero and the message names the store path it expected
- **Test:** `tests/test_hermes_smoke.py::test_a_run_that_writes_no_store_is_a_named_failure`

#### Scenario: an unreadable store is still a named failure

- **Given** a `state.db` that exists but is not a sqlite store
- **When** the smoke runs
- **Then** it exits non-zero saying `no readable sessions store` and never calls the model
- **Test:** `tests/test_hermes_smoke.py::test_a_missing_transcript_is_a_named_failure`

### Requirement: the proof itself is unchanged

The smoke MUST still pass only on a session with a `role='tool'`, `tool_name='terminal'` result that
carries `smoke-ok:<nonce>`, and a final answer carrying the same string; a text-only transcript, a
non-terminal tool, or a tool counter MUST still fail.

WHEN the store is judged
THEN the nonce-in-a-terminal-result rule decides the verdict, exactly as before.

#### Scenario: a text-only transcript still fails

- **Given** a session with an assistant answer and no tool call
- **When** the smoke evaluates it
- **Then** the verdict names the model that answered without calling a tool
- **Test:** `tests/test_hermes_smoke.py::test_a_text_only_transcript_is_a_failure`
