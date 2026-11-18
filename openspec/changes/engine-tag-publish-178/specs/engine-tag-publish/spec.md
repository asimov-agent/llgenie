## ADDED Requirements

### Requirement: PR-scoped producer publishes the unique pin only
A producer run dispatched for a pull-request repin SHALL publish only the immutable
pinned tag and SHALL NOT move `:<arch>` or `:latest`. The skip SHALL be printed as a
named note that cites the main run as the mover.

#### Scenario: PR-scoped push publishes one ref
- WHEN `push()` runs with the moving gate disabled for a spec whose publish refs are the pin plus `:<arch>`
- THEN only the pinned ref is pushed, no `docker tag` for the moving refs occurs, and the note names issue #178

#### Scenario: PR repin dispatch carries the scope flag
- WHEN `engine_build_trigger.py` dispatches a cell for a PR
- THEN the dispatch fields include `moving_tags=false`

### Requirement: PR-scoped published pull measures the pin alone
A published-binary leg running in a PR-scoped producer run SHALL verify the pulled pinned
ref without requiring digest equality with the moving tags.

#### Scenario: alias digest differs during a wave
- WHEN `pull_published()` runs with the moving check disabled and the `:<arch>` alias points at a different digest
- THEN the pull still returns the local tag and the note names the skipped moving check

#### Scenario: main-scoped pull keeps the equality check
- WHEN `pull_published()` runs with default settings and the alias digest differs
- THEN it still fails with the digest mismatch

### Requirement: moving tags move only on main-scope producer runs
The `engine-build` producer SHALL default to moving (all refs published) and SHALL move the
architecture tags only in runs whose dispatch did not disable moving.

#### Scenario: default dispatch keeps today's main behaviour
- WHEN `engine-build.yml` is dispatched without the `moving_tags` input
- THEN the push step runs without `--no-moving` and publishes the pin and the moving refs

## MODIFIED Requirements

### Requirement: published image verification
`make test-published-engine` SHALL verify the exact published tag: it pulls the pinned ref
with no local build available, verifies its registry digest, and — in main-scope runs —
requires the same digest on the engine's `:<arch>` tag (and `:latest` when present). In a
PR-scoped run (`MOVING=0`) it SHALL verify the pinned digest alone, because the main run has
not yet moved the alias.

#### Scenario: main run verifies alias equality
- WHEN `make test-published-engine ENGINE=<id> ARCH=<arch>` runs on a main-scope producer
- THEN it passes only when digest(pin) == digest(:<arch>)

#### Scenario: PR-scoped leg passes mid-wave
- WHEN the same target runs with `MOVING=0` while another PR's pin holds the alias
- THEN it passes on the pinned digest alone
