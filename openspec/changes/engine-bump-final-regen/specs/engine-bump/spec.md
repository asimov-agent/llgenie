## ADDED Requirements

### Requirement: A bump commit lands with its generated companions in sync

The engine-bump producer SHALL verify, after every write step of a bump (pin, apply, asserts, sync,
regen, frozen-hash rewrites, companion notes), that `make check-engine-params` reports the committed
params AND `containers/engines/binaries.json` as exactly what the skills generate. When the check
names a stale generated file, the producer SHALL re-run `make generate-engine-params ENGINE=<id>`
once and re-check; a second stale verdict SHALL hard-fail the bump rather than commit a tree whose
binaries manifest lags its own skill.

#### Scenario: A post-regen skill rewrite desyncs the binaries manifest

- **WHEN** a bump's final writes leave `containers/engines/binaries.json` behind the skill's version
- **THEN** the final `make check-engine-params` names it, the producer regenerates once, and the
  commit carries the regenerated manifest
- **AND** the bump log's `regen:` set includes the regenerated paths

#### Scenario: Regen cannot converge

- **WHEN** a second `make check-engine-params` after the one re-regen still names a stale file
- **THEN** the bump hard-fails with the checker's verdict quoted, and no bump PR is opened

### Requirement: A desynced bump lane is re-armed with its regenerated manifest

The change closing issue #3065 SHALL also land the regenerated manifest on the red lane it diagnoses:
`chore/engine-bump-ollama` (PR #3029) carries a commit regenerating `containers/engines/binaries.json`
at its head, so the four `engine-build-ollama-*` probes and the unit gate can go green at that head.

#### Scenario: The ollama lane turns on the regenerated manifest

- **WHEN** the regenerated manifest is pushed to `chore/engine-bump-ollama`
- **THEN** `make check-engine-params` is green at the new head and the engine-build probes read
  `.../ollama/0.40.17/bin/ollama`
