## ADDED Requirements

### Requirement: the committed-scope pin gate compares arch-alias digests when the alias knob is on
When the alias check is enabled, the committed-scope published-pin check SHALL, for every cell whose committed pin tag resolves, also resolve that cell's `:<variant>` alias manifest and compare the two digests. An aligned alias SHALL print an `ALIAS OK` line; an alias whose digest differs from the committed pin digest, or which resolves no manifest at all, SHALL print an `ALIAS LAG` line naming the alias ref and both digests, SHALL emit the same `[select] <engine> <variant> <tag-suffix>` dispatch-contract line as an unpublished tag, and SHALL red the check.

#### Scenario: aligned aliases stay green
- **WHEN** the knob is on and every cell's `:<variant>` alias digest equals its committed pin-tag digest
- **THEN** the check exits 0 and its output carries an `ALIAS OK` line per cell.

#### Scenario: a lagging alias selects its cell for the moving push
- **WHEN** the knob is on and a cell's `:<variant>` alias resolves a manifest whose digest differs from the committed pin tag's digest
- **THEN** the check exits 1, prints `ALIAS LAG` naming the alias ref and both digests, and prints the cell's `[select]` line so the caller's dispatch machinery can queue the exact repair.

#### Scenario: an alias that resolves nothing is a lag
- **WHEN** the knob is on, a committed pin tag resolves, and the cell's `:<variant>` alias resolves no manifest
- **THEN** the check exits 1 with an `ALIAS LAG` line stating the alias is absent and the cell's `[select]` line.

#### Scenario: the alias comparison is opt-in per caller
- **WHEN** the knob is unset (every PR lane, `ci-hf-live`, every local `make check-engine-pins-published` run)
- **THEN** each cell's pin tag is probed exactly once, no alias ref is probed, and a lagging alias does not change the verdict — tag-existence semantics are unchanged.

#### Scenario: the knob arrives through the environment and a malformed value is loud and off
- **WHEN** `ENGINE_PINS_ALIAS` is set to a value that is neither on (`1`/`true`) nor off (`0`/`false`)
- **THEN** the check prints a WARN naming the bad value to stderr and behaves as if the knob were unset.

### Requirement: registry-liveness runs the committed gate with the alias check on
The `registry-liveness` workflow SHALL set `ENGINE_PINS_ALIAS=1` on both of its `make check-engine-pins-published ALL=1` invocations (the fleet gate and the dispatch gate) and no other workflow SHALL set it, so a lagging alias reddens the liveness gate and flows through the existing coalesced `push=true` engine-build dispatch that moves `:<arch>`/`:latest` and retests the published leg.

#### Scenario: the wiring is pinned by a test
- **WHEN** `make test-unit` runs the gate's workflow-wiring test
- **THEN** it reads `.github/workflows/registry-liveness.yml` and fails if either `ALL=1` invocation lacks the `ENGINE_PINS_ALIAS` env or any workflow outside registry-liveness sets it.
