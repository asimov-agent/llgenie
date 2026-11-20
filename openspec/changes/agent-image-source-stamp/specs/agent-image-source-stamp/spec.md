# agent-image-source-stamp — spec of record

## ADDED Requirements

### Requirement: the agent image build stamps its tree's source hash

`scripts/ci_images.py` MUST stamp every agent image it builds — publish (`buildx build --push`)
and local fallback (`docker build`) — with the OCI label `llgenie.agent.source` whose value is the
12-hex content hash `ci_images.tag("agent")` of the tree the build ran from. Other images' builds
MUST NOT change.

#### Scenario: a publish stamps the label
- **WHEN** `ci_images.py publish agent` builds and pushes a new hash
- **THEN** the `buildx build` command line carries `--label
  llgenie.agent.source=<the same 12-hex tag the image is tagged with>`

#### Scenario: a local fallback build stamps the label
- **WHEN** `ci_images.py ensure agent` cannot pull the published tag and builds
  `llgenie/agent:latest` locally
- **THEN** the `docker build` command line carries `--label llgenie.agent.source=<tree tag>`

### Requirement: source-check names a stale published agent image

`scripts/ci_images.py` MUST provide a `source-check` verb that reads the `llgenie.agent.source`
label off the resolved local agent image (`docker inspect`) and compares it against the tree's
computed tag. A match exits 0. A missing label or a differing value exits non-zero printing the
tree's hash, what the image carried (or `no source label`), and the named remedy — dispatch
`publish-agent-image.yml` on main (issue #2935). `make agent-image-source-check` MUST wrap it.

#### Scenario: the stale published latest is refused
- **WHEN** the resolved `llgenie/agent:latest` carries no source label (every image published
  before this change) or carries one from an older tree
- **THEN** `make agent-image-source-check` exits non-zero naming both hashes and issue #2935

#### Scenario: a fresh image passes
- **WHEN** the resolved image's label equals the tree's computed agent tag
- **THEN** the check exits 0 printing the matching hash

### Requirement: the agent-leg preflight refuses a stale image before hermes-smoke

`.github/actions/agent-leg/action.yml` MUST run `make agent-image-source-check` in the preflight
phase, after the JEV / shell-keys proofs and BEFORE `make hermes-smoke`, under the same
`routing_smoke` opt-in as the smoke step. A leg that would crash `hermes-smoke` on a stale image
MUST instead fail at the source-check step.

#### Scenario: ordering
- **WHEN** the composite action's steps are read
- **THEN** `make agent-image-source-check` appears before `make hermes-smoke`, guarded by
  `inputs.phase == 'preflight' && inputs.routing_smoke == 'true'`

#### Scenario: legs without the routing smoke are unchanged
- **WHEN** a leg passes `routing-smoke: false`
- **THEN** neither the source-check nor `hermes-smoke` runs for that leg
