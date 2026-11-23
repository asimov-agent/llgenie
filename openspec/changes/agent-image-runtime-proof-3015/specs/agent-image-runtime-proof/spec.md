# agent-image-runtime-proof — spec of record

## ADDED Requirements

### Requirement: the publish lane proves the pushed image came from this tree

`.github/workflows/publish-agent-image.yml` MUST run `make agent-image-pull` followed by
`make agent-image-source-check` after `make publish-agent-image` and before any other
post-publish verification step. The pull is required because `buildx build --push` does not load
the just-built image on the runner. A published image whose `llgenie.agent.source` label is missing
or differs from the tree hash MUST redden the lane with both hashes named; the existing
`make hermes-smoke` step MUST remain after this step.

#### Scenario: a stale tag cannot pass the lane

- **WHEN** the publish step resolves an image whose source label is absent or is not this tree's hash
- **THEN** `make agent-image-source-check` exits non-zero and the publish lane stops before the profile and prompt checks

#### Scenario: a fresh tag continues to the bot proofs

- **WHEN** the resolved image carries this tree's source hash
- **THEN** the lane continues to the lane-resolution check and then to `make hermes-smoke`

### Requirement: every declared bot lane must resolve inside the published image

`scripts/agent_image_profiles_check.py` MUST, when invoked with `--resolve`, check for every lane
in `agents/manifest.json` both that `$HERMES_HOME/profiles/<lane>/config.yaml` exists and that
`hermes -p <lane> skills list --source local` exits zero inside that image. It MUST print
`RESOLVE OK <lane>` or `RESOLVE FAIL <lane>: <reason>` per lane and exit non-zero when any lane
fails to resolve. It MUST NOT require a model key or make a model call for this proof.

#### Scenario: a provisioned but unresolvable lane is refused

- **WHEN** a lane's config file exists but `hermes -p <lane> skills list --source local` exits non-zero
- **THEN** the seam prints `RESOLVE FAIL <lane>: ...` naming the failure and exits 1

#### Scenario: all declared lanes resolve

- **WHEN** every manifest lane has a config file and Hermes resolves each one locally
- **THEN** the seam prints `RESOLVE OK <lane>` for each and exits 0

#### Scenario: the hermes CLI is unavailable

- **WHEN** `--resolve` is requested but `hermes` is not on PATH
- **THEN** the seam fails loudly naming the missing CLI, never skipping the proof

### Requirement: the publish lane runs the resolution seam before the prompt smoke

`mk/agents.mk::_agent-image-profiles-check` MUST invoke `scripts/agent_image_profiles_check.py
--resolve`; `.github/workflows/publish-agent-image.yml` MUST order the steps as publish → source
check → profile/resolution check → `make hermes-smoke`. All workflow commands MUST remain
Makefile targets.

#### Scenario: step ordering in the workflow

- **WHEN** the publish job steps are read
- **THEN** the source check precedes the profiles check and both precede the prompt smoke

#### Scenario: the in-image target carries the flag

- **WHEN** the internal target is read
- **THEN** it calls the real seam with `--resolve` and the same `agents/manifest.json`
