# agent-leg-model-route — spec delta

## ADDED Requirements

### Requirement: A bot leg names the model that served it

Every Hermes bot leg that runs `hermes -p <lane>` SHALL print one report line of the form
`model-route: <model-id>` after the leg's Hermes run finishes, naming the model recorded in the
lane's Hermes session store (`sessions.model`) for the newest session started inside the leg's
run window. The report SHALL be read from the profile home's `state.db`
(`$HERMES_HOME/profiles/<lane>/state.db`) when that home exists, falling back to the global
`$HERMES_HOME/state.db` only when it does not. The report SHALL NOT change the leg's exit
status: the leg fails exactly when `hermes` failed, and the report runs in between.

#### Scenario: A served leg reports its model

- **WHEN** a bot leg's Hermes run finishes and the lane store carries a session started inside the leg window with a recorded model
- **THEN** the leg log contains exactly one `model-route: <model-id>` line naming that model, and the leg's exit status is Hermes' own status

#### Scenario: A fallback-served leg reports the fallback

- **WHEN** the chain hopped and the last-resort model served the leg
- **THEN** the report line names the last-resort model id, making fallback usage measurable from the run log alone

### Requirement: An unevidenced model route fails loudly, never fabricated

When the lane store is missing, no session started inside the leg window, or the session carries
no model value, the report SHALL exit non-zero with a named failure and SHALL NOT print a
`model-route:` line. A leg SHALL never report a model it cannot evidence.

#### Scenario: Missing store

- **WHEN** neither the profile home's store nor the global store exists (or is unreadable)
- **THEN** the report exits non-zero and names the store paths it tried

#### Scenario: No session inside the window

- **WHEN** the store exists but holds no session started at or after the leg's start time
- **THEN** the report exits non-zero and states that no session was started inside the window

### Requirement: The model-route line carries only a model id

The report SHALL print only the `sessions.model` value on the line — never a key, endpoint from
the config, or any environment value — and the secret-output gate SHALL stay green with the
report wired in.

#### Scenario: Secret gate

- **WHEN** `make check-secret-output` runs against the tree carrying the report
- **THEN** it exits zero

### Requirement: hermes-smoke reports the serving model of its session

`make hermes-smoke` SHALL print a `model-route: <model-id>` line naming the model recorded for
the session the smoke created, in addition to its tool-capability verdict.

#### Scenario: Passing smoke carries the line

- **WHEN** a smoke run passes against an agent image
- **THEN** the smoke output contains `model-route: ` naming the session's model id
