## ADDED Requirements

### Requirement: Hermetic full-shape accounting for the pick matrix

The hermetic unit suite (`make test-unit`) SHALL assert, with the Hub and engine registry
stubbed, that `matrix()` accounts for every card-gated model exactly once: a model enumerated
by the card gate (`trend_list(registry, gb, ram)`) appears in `permutations` (offered, with a
download plan) OR in `skipped` with a non-empty reason — never in both and never absent — at
each card size the suite covers (8, 16 and 48 GB). A mutation that silently drops a gated model
from both homes SHALL redden `make test-unit` with zero network I/O.

#### Scenario: every gated model is offered or skipped
- **WHEN** `matrix()` runs on the synthetic registry at 8 GB, 16 GB and 48 GB with the default band
- **THEN** the union of `permutations` ids and `skipped` ids equals the card-gate enumeration for that card, the two sets are disjoint, each model appears at most once in `skipped`, and every skip row carries a non-empty `why`

### Requirement: The band narrows only the offered set, hermetically

The hermetic unit suite SHALL assert that the VRAM band narrows only which models `matrix()`
offers: an off-band model the card gate fits is skipped naming the band; naming the band
explicitly (the `vram_range` argument or `LLGENIE_VRAM_RANGE`) re-admits it; the card-gate
enumeration itself is identical under every band variant; a CPU/Apple-only row (no numeric VRAM
tier) is never band-excluded; and `offer()`'s default view applies no band at all (issue #2047's
shape must stay a row).

#### Scenario: band variants share the same gate
- **WHEN** `matrix()` runs at 16 GB with the default band, with `vram_range=(4, 64)`, and with `LLGENIE_VRAM_RANGE="4, 64"`
- **THEN** the offered id set under the widened band equals the default offered set plus exactly the off-band-but-fitting model, the default skip row for that model names `VRAM band`, the widened runs carry no band skip row, and the `trend_list` gate enumeration is the same in all three runs

#### Scenario: skip reasons stay distinct
- **WHEN** a fitting model has no engine image for the host arch, and another in-band model's smallest download exceeds the budget
- **THEN** the first is skipped with the no-engine-image reason and the second with the no-download reason, and neither reason names the band
