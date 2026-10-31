# Engine capacity mapper: the docs-cited sync guard-rail (issue #1214)

`data/engine-capabilities.json` is the canonical, machine-checkable table of what each
shipped engine REALLY supports — its docker arch types and the model formats it reads,
each row a fact read from the engine's own upstream README/releases (the `cite:` field),
never the trending-store's one-line auto-registration note. `make check-engine-capabilities`
(`scripts/check_engine_capabilities.py`) proves every claim the tree makes is a docs-cited
SUBSET of it:

- **E1** a skill's `backends:` that leaves the mapper → a human-authored arch drift.
- **E2** a skill's `formats:` that leaves the mapper → a format the engine cannot read.
- **E3** a params `variants` key that leaves the mapper → a generated arch the engine lacks.
- **E4** a skill that declares a Prism-only ternary tensor type (`GGML_TYPE_PQ2_0`=142 /
  `PTQ1_0`=143, or its `PQ2_0`/`PTQ1_0` quants) but whose mapper row is not `ternary: true`
  → a ternary GGUF that would hang a stock llama.cpp server at load. (`TQ1_0`/`TQ2_0` are
  UPSTREAM ternary and do NOT trigger E4.)
- **E5** a shipped skill with no mapper row, or a mapper row with no skill.

Only the PrismML fork (`llama.cpp-prism`) is `ternary: true` today; stock llama.cpp and
the LaurentZuijdwijk fork are deliberately false.

## Why it exists (the faulty-store path this closes)

`sync_registry` copies the upstream store's `engines` dict with shape + README-order
contract checks only. Previously a store entry that named an arch the engine never
supported, or a model served by an engine that cannot read its format, landed unverified
and only failed at build — or hung at serve for ternary on stock. Now the mapper is the
guard: the sync work (new engine, new arch, new format) must add the docs-cited mapper
row first, or `check-engine-capabilities` reds in the same `ci-unit` stage that already
runs `check-engine-coverage` / `check-engine-source` / `check-engine-skill-gap`.

Shipment: `make check-engine-capabilities` (CI gate) + `make engine-capabilities-report`
(census) added to `ci-unit`, `.PHONY`, `docs/ENGINES.md`, and `issue_bot_gates.DEFERRED`
(#475). Tests in `tests/test_engine_capabilities.py` prove each of E1–E5 reds against a
synthetic tree and that the real tree passes.

## Using it

```bash
make check-engine-capabilities       # CI gate
make engine-capabilities-report      # census: engine -> archs + formats + TERNARY flag
make check-engine-source             # the sibling source-build gate (existing)
```
