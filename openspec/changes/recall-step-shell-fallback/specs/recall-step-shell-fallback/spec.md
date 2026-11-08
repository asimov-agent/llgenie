# recall-step-shell-fallback

## ADDED Requirements

### Requirement: the orchestrator recall step carries a shell fallback pinned to the live daemon

STEP 2 (RECALL) of the versioned procedure MUST provide BOTH the agent-tool path (when the turn
has it) and a shell fallback that pins the host, port and path explicitly — `curl -s -m 8 -X POST
http://127.0.0.1:9177/v1/default/banks/<lane-bank>/memories/recall -d '{"query":"<failure class>","limit":3}'`
— never a CLI default. The bank id MUST be the lane's own (`llgenie-planner`), not a placeholder
that 404s.

WHEN a turn lacks the `hindsight_recall` agent tool and runs the fallback
THEN the fallback POSTs to 127.0.0.1:9177 with the lane's own bank id and the recall answers.

#### Scenario: the fallback returns the known class from the lane's bank

- **Given** the hindsight daemon is healthy on 127.0.0.1:9177
- **When** the STEP 2 fallback POSTs `{"query":"check-pr-acceptance write-back","limit":2}` to
  `/v1/default/banks/llgenie-planner/memories/recall`
- **Then** the response carries a non-empty `results` array and the class is returned
- **Test:** `tests/test_procedure_recall_step.py::test_recall_fallback_returns_nonempty_results`

### Requirement: the step distinguishes a wrong command from a dead daemon

The step MUST carry a health probe (`curl -s http://127.0.0.1:9177/health`) so that a failed
recall against a daemon whose health probe succeeds is read as a wrong command, not a dead
subsystem. The step text MUST forbid reporting the instrument absent without running the fallback,
and MUST state the port is 9177 while 8888 appears only commented-out in `hermes.env`.

WHEN the fallback is pointed at the wrong default port 8888 and the 9177 health probe is run
THEN the 8888 attempt fails while 9177/health succeeds, distinguishing a wrong command from a dead
daemon.

#### Scenario: the wrong-port negative control proves the distinction

- **Given** the daemon is healthy on 127.0.0.1:9177 and nothing listens on 8888
- **When** the recall/health attempt is pointed at 8888 (the CLI default) and 9177/health is probed
- **Then** the 8888 attempt fails, `9177/health` returns `{"status":"healthy"}`, and the check
  reads the failure as a wrong command
- **Test:** `tests/test_procedure_recall_step.py::test_wrong_port_fails_while_health_probe_succeeds`

### Requirement: a step naming an agent tool the runner lacks states its durable channel

A tool-dependent step that genuinely cannot be done from a shell (`message_agent` is an agent
tool, not a binary) MUST say so and name the durable substitute — the board task plus an on-issue
comment — rather than leaving a dead tool call in the procedure that a runner without the agent
toolset cannot execute.

WHEN a runner without the agent toolset reaches a message_agent step
THEN the step names the board task + on-issue comment as the durable channel and stays executable.

#### Scenario: message_agent steps carry a durable substitute

- **Given** the versioned procedure's steps 6 and 11 reference `message_agent`
- **When** the "A step must not name a mechanism the runner lacks" section is read
- **Then** it states that the durable channel is the board task plus an on-issue comment, so a
  cron turn without the agent toolset can still execute the step

### Requirement: the endpoint is discovered, not guessed

The recall path MUST be discoverable rather than hardcoded by guesswork:
`curl -s http://127.0.0.1:9177/openapi.json` lists `/v1/default/banks/{bank_id}/memories/recall`; a
guessed path or port must not be the basis for the step.

WHEN the openapi.json of the live daemon is read
THEN its `paths` include `/v1/default/banks/{bank_id}/memories/recall`, the path the fallback uses.

#### Scenario: the openapi listing names the recall path the fallback uses

- **Given** the future producer of the step may not know the recall path from memory
- **When** `curl -s http://127.0.0.1:9177/openapi.json` is read
- **Then** its `paths` include `/v1/default/banks/{bank_id}/memories/recall`, which is the exact
  path the fallback POSTs to
- **Test:** `tests/test_procedure_recall_step.py` (the live openapi discovery in the issue's
  implementation detail)

