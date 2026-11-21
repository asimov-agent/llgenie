## MODIFIED Requirements

### Requirement: the committed-scope pin gate compares arch-alias digests when the alias knob is on
When the alias check is enabled, the committed-scope published-pin check SHALL, for every cell whose committed pin tag resolves, also resolve that cell's `:<variant>` alias manifest and compare the two digests. An aligned alias SHALL print an `ALIAS OK` line; an alias whose digest differs from the committed pin digest, or which resolves no manifest at all, SHALL print an `ALIAS LAG` line naming the alias ref and both digests, SHALL emit the routing contract line `[aliasmove] <engine> <variant> <tag-suffix> <pin-digest>` — the repair for a resolved pin whose alias lags is a registry-side manifest move, not a build — and SHALL red the check. The `[select] <engine> <variant> <tag-suffix>` build-dispatch contract SHALL be emitted only for cells whose committed pin tag itself is absent from the registry.

#### Scenario: aligned aliases stay green
- **WHEN** the knob is on and every cell's `:<variant>` alias digest equals its committed pin-tag digest
- **THEN** the check exits 0 and its output carries an `ALIAS OK` line per cell.

#### Scenario: a lagging alias selects a manifest move, not a build
- **WHEN** the knob is on and a cell's `:<variant>` alias resolves a manifest whose digest differs from the committed pin tag's digest
- **THEN** the check exits 1, prints `ALIAS LAG` naming the alias ref and both digests, prints the cell's `[aliasmove]` line carrying the committed pin digest, and prints NO `[select]` line for that cell, so the build-dispatch machinery never queues an engine build for it.

#### Scenario: a CPU-only engine's lag selects the move that can actually heal it
- **WHEN** the lagging cell belongs to an engine in `DEFAULT_CPU_ONLY` (e.g. `vllm` at `cuda` or `rocm`), whose GPU variants are structurally absent from every build matrix and dispatch sweep
- **THEN** the gate routes it exactly like any other lag — an `[aliasmove]` line with the pin digest and no `[select]` line — because the manifest move needs no GPU and no build.

#### Scenario: an alias that resolves nothing is a lag routed to the move
- **WHEN** the knob is on, a committed pin tag resolves, and the cell's `:<variant>` alias resolves no manifest
- **THEN** the check exits 1 with an `ALIAS LAG` line stating the alias is absent and the cell's `[aliasmove]` line.

#### Scenario: a manifest-unknown cell keeps the build dispatch
- **WHEN** a committed pin tag itself resolves no manifest
- **THEN** the check still emits the unchanged `[select] <engine> <variant> <tag-suffix>` line and no `[aliasmove]` line for it, and the #2579 coalesced `push=true` dispatch repairs it as before.

#### Scenario: the alias comparison is opt-in per caller
- **WHEN** the knob is unset (every PR lane, `ci-hf-live`, every local `make check-engine-pins-published` run)
- **THEN** each cell's pin tag is probed exactly once, no alias ref is probed, and a lagging alias does not change the verdict — tag-existence semantics are unchanged.

#### Scenario: the knob arrives through the environment and a malformed value is loud and off
- **WHEN** `ENGINE_PINS_ALIAS` is set to a value that is neither on (`1`/`true`) nor off (`0`/`false`)
- **THEN** the check prints a WARN naming the bad value to stderr and behaves as if the knob were unset.

## ADDED Requirements

### Requirement: a lagging alias is healed by a registry-side manifest move verified against the pin digest
The repository SHALL provide `scripts/engine_alias_move.py` (make target `engine-alias-move`, args `ENGINE=`, `VARIANT=`, `SUFFIX=`, `DIGEST=`) that moves the `:<variant>` alias tag of a repository engine to a committed pin digest using `docker buildx imagetools create` — a registry-side manifest re-point that builds nothing — and SHALL verify the move by re-resolving the alias digest against the pin digest through the existing `engine_image._digest_http` authority. It SHALL refuse a malformed contract: the four fields must be present and the digest must match `sha256:` followed by 64 hex characters. It SHALL print `[alias-move] MOVED <alias-ref> -> <digest>` on success (exit 0) and `[alias-move] FAIL …` (exit non-zero) when the post-move digest does not match.

#### Scenario: the move is a manifest re-point, not a build
- **WHEN** the mover runs for a valid contract
- **THEN** the only external command it issues to move the tag is `docker buildx imagetools create -t <registry>/<engine>:<variant> <registry>/<engine>@<pin-digest>` and no engine build, engine container, or engine execution takes place.

#### Scenario: the move is verified after it lands
- **WHEN** the registry accepted the manifest move
- **THEN** the mover resolves the alias again and prints the MOVED line naming the alias ref and the digest only when the resolved digest equals the pin digest; a mismatch prints FAIL and exits non-zero.

#### Scenario: a malformed contract is refused
- **WHEN** `DIGEST` is missing or is not `sha256:<64 hex>`, or `ENGINE`, `VARIANT`, or `SUFFIX` is missing
- **THEN** the mover prints the refusal naming the bad field and exits non-zero without contacting the registry.

### Requirement: registry-liveness heals alias-lagging cells before its fleet gate, without dispatching a build
The `registry-liveness` workflow SHALL run a heal step BEFORE the full-fleet committed-tag pin-validity gate: it runs the knobbed gate once, collects every distinct `[aliasmove]` line, refuses a contract-violating line, and for each valid line runs `make engine-alias-move` with the line's engine, variant, suffix, and pin digest, under a `packages: write` permission with a GHCR login using the job token. It SHALL skip the heal while a same-head publisher run is still in flight (the #2592 deferral: a producer may itself be mid-move). After the heal, the existing fleet gate re-probes with fresh digests, so a healed cell reads ALIAS OK in the same run, and a cell the heal could not move stays a red gate naming it.

#### Scenario: a CPU-only lag cell is healed in-lane
- **WHEN** the gate classifies `vllm` `cuda`/`rocm` as alias lag (resolved pin, stale alias) and no publisher is in flight
- **THEN** the run moves both aliases via `make engine-alias-move` and the fleet gate reports them ALIAS OK, with NO `gh workflow run engine-build.yml` dispatch carrying `engine=vllm` for those cells.

#### Scenario: manifest-unknown gaps still ride the sweep
- **WHEN** the gate also reports cells with no committed manifest (`[select]` lines)
- **THEN** the existing coalesced `push=true` dispatch step still runs for them unchanged, and those cells are never sent through the manifest move.

#### Scenario: the heal defers while a same-head publisher is in flight
- **WHEN** the workflow's publisher-in-flight flag is true
- **THEN** the heal step prints the deferral reason, moves nothing, and the run proceeds to its existing publisher-failure handling.

#### Scenario: a malformed contract line reddens the heal step
- **WHEN** an `[aliasmove]` line carries fewer than five fields or a digest that is not `sha256:<64 hex>`
- **THEN** the heal step names the violating line and exits non-zero instead of moving any tag.
