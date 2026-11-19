# Agent-image CI verification — the build lane proves the image it publishes is usable

## ADDED Requirements

### Requirement: the agent publish lane asserts the built image carries every manifest profile

The `publish-agent-image.yml` publish job SHALL run `make agent-image-profiles-check` after its publish
step. That target SHALL execute the agent image and fail non-zero, naming each lane, when a profile
declared in `agents/manifest.json` has no `$HERMES_HOME/profiles/<lane>/config.yaml` inside the image.
The lane SHALL NOT hand-roll a docker invocation for this assertion; it calls the Makefile target.

#### Scenario: a manifest lane is missing from the image

Given an agent image whose baked profiles lack one of the 13 `agents/manifest.json` lanes
When `make agent-image-profiles-check` runs against that image
Then the target exits non-zero and prints `MISSING <lane>` for each absent lane

#### Scenario: the lane is present in CI

Given `publish-agent-image.yml`
When its publish job's steps are read
Then a `make agent-image-profiles-check` step appears after the `make publish-agent-image` step

### Requirement: the agent publish lane smoke-tests the published image with a real prompt

The publish job SHALL run `make hermes-smoke` after the publish step, passing `NOUS_API_KEY` from
`secrets.NOUS_PORTAL_API_TOKEN`. The smoke run SHALL target the image the same run just published
(`ensure agent` pulls `:latest`, which the publish moves onto the new content hash) and SHALL prove one
real Hermes call that uses its tool, asserting the per-run nonce from the redacted transcript; the model
chain comes from the profile's own `config.yaml` (no `-m`/alias flag post-#2929).

#### Scenario: the published image cannot answer a prompt

Given a published `agent:latest` whose Hermes cannot complete a smoke call (missing profile, broken
chain config, failed install)
When the publish job reaches its `make hermes-smoke` step
Then the lane reddens on that step instead of exiting green after the push

#### Scenario: prompt proof uses the lane credential shape

Given the smoke step's env
When `secrets.` references are read from it
Then the key passed is `NOUS_PORTAL_API_TOKEN` (the credential every other agent lane already passes)

### Requirement: verification reaches CI only through Makefile targets

Every command the publish lane's verification half runs SHALL be a `make` target
(`agent-image-profiles-check`, `hermes-smoke`); the workflow SHALL NOT call `python3 scripts/...` or a
raw `docker run` for the verification.

#### Scenario: wiring guard stays green

Given the repo tree carrying this change
When `make check-wiring` and `make lane-preflight` run
Then both exit zero with the new target wired to the publish lane
