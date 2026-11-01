# Tasks — card-gate-measured-vram

- [x] `fits()` admits on measured evidence: a `ran on` card ≤ N, else `vram_min` ≤ N, else the
      stated `weight_gb` ≤ N, with `vram_tier` only when the store states none of them
      (#669); `system_ram_min` stays a hard floor.
- [x] `trend_list()` orders a card's list by the vendored README's `### Up to N GB` tier
      ranking, then the rows it does not rank in the store's own trend order.
- [x] The store's ranking is computed in code (`band → trend score → posts → peak t/s`), so
      the file's position is not load-bearing; measured identical to the committed order
      (112/112 rows).
- [x] `tests/test_card_gate_measured_vram.py` pins each scenario of
      `specs/card-gate/spec.md`, with `# Given / # When / # Then` markers.
- [x] The regression test is proved red-then-green: reintroducing the `vram_tier` read in
      `fits()` reds it, restoring `vram_min`/run evidence greens it; both outputs recorded.
- [x] Every model the vendored README's `### Up to 8/12/16/24/32/48 GB` table places is
      admitted at that tier (0 missing), measured against the vendored store.
- [x] `tests/test_trend_list_acceptance.py` AC1 asserts the new rule (membership from
      `mp.fits()`, order from the tier table then the computed store order).
- [x] `tests/test_trend_pick.py` order helper derives the card's order from the product, not
      from the store's positions.
- [x] `make render-trend-list-matrix` regenerated and committed (the committed list moves with
      the rule); `make check-trend-list-matrix` green.
- [x] `README.md` and `agent-wiki/` state the card → model → server rule in one place (which
      field admits a model, what the order is, what a bigger card's figure is not); `CHANGES.md`
      indexes the note.
- [x] RAM-floor precedence carries #1072's measured-governs ruling exactly (#1089): the
      admitting run's own `system_ram_min`, else the RAM its `hardware` names, else the model's
      declared figure only when the evidence states none — pinned in BOTH directions (run names
      less AND more than the contract), plus the no-host-RAM widening stated deliberately.
- [x] The criterion of record states the precedence once and verbatim: `specs/card-gate/spec.md`
      no longer reads "the host's RAM SHALL also be at least [the store's]" unqualified, and
      `docs/ARCHITECTURE.md` names the evidence-ordered rule, not contract-governs (#1089).
- [x] `tests/test_card_gate_measured_vram.py` pins both precedence directions + the no-host
      widening (`test_the_system_ram_floor_still_applies` updated to assert declared-rewrite
      invariance; new `test_the_run_floor_governs_when_the_run_names_more_ram_than_the_contract`
      and `test_fits_without_host_ram_applies_the_card_evidence_only`); `git grep system_ram_min`
      on the spec/ARCHITECTURE shows no unqualified contract-floor sentence (#1089).
- [x] `make openspec-validate NAME=card-gate-measured-vram` green.
- [x] `make test-unit` green with the new rule, and `make lint` / `make check-docs` green.
