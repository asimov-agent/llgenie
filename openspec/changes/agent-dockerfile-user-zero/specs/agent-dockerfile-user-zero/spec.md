# Spec delta — agent-dockerfile-user-zero

## ADDED Requirements

### Requirement: Agent image Dockerfile never spells a root USER instruction

The agent image's Dockerfile (`containers/agent/Dockerfile`) SHALL grant build privileges only through the numeric form `USER 0`, and its final `USER` instruction SHALL name a non-root user. The literal instruction `USER root` SHALL NOT appear in the file, because the pinned semgrep lane's `last-user-is-root` rule cannot resolve its exemption span in a file of this size and flags any literal `USER root` in it (issue #2970).

#### Scenario: scan stays clean on the agent Dockerfile

- **WHEN** `make security-scan TOOL=semgrep` runs on the tree containing the fix
- **THEN** the report contains no `last-user-is-root` finding for `containers/agent/Dockerfile`

#### Scenario: the privilege shape is pinned by a test

- **WHEN** the unit battery runs `tests/test_agent_image_refresh.py`
- **THEN** a test asserts the agent Dockerfile has no `USER root` line, has a `USER 0` line, and its last `USER` names a non-root user

#### Scenario: build privileges are unchanged

- **WHEN** the agent image is built from the edited Dockerfile
- **THEN** every `RUN` before the final non-root `USER` executes as uid 0, exactly as before the edit
