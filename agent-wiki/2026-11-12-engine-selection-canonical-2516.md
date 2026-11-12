# 2026-11-12 — engine selection is canonical: fleet dispatch consumes committed ids, not package URLs (issue #2516)

- The registry-liveness self-remediation wave for `aa700cf27` (#2517) dispatched 28 scoped
  `engine-build push=true` runs; nine "completed success" runs built nothing. They were named
  `engine-build-none-none`: the dispatch reconstructed engine ids from GHCR package URLs, but
  package names replace dots with dashes (`params['id'].replace('.', '-')`), so `llama.cpp`
  reached  `engine-build.yml` as `llama-cpp`, matched no committed id, emitted the `none` placeholder
  row and exited 0 — a green no-op.
- Introspection: the `[select]` line is the canonical contract. `scripts/check_engine_pins_published.py`
  now emits one `[select] <engine-id> <variant> <tag>` line per unpublished cell on the `--all`
  sweep, carrying the committed id (dots intact). `registry-liveness.yml`'s dispatch step consumes
  ONLY those lines; no engine id is derived from a package URL anymore.
- matrix hard-fail: `scripts/engine_image.py matrix()` exits non-zero naming the selection when an
  explicit `--engine`/`--arch` resolves to zero committed cells (`no committed engine id llama-cpp`,
  `llama.cpp has no committed variant metal`). The `none` placeholder remains only for the unscoped
  sweep (`--changed` with nothing moved, whole-fleet), keeping the intentional no-op. This reddens
  `make engine-build-matrix ENGINE=<typo>` and `make build-engines ENGINE=<typo>`, today silent no-ops.
- Verified: `matrix --engine llama-cpp` rc=1 naming the id; `--engine llama.cpp --arch metal` rc=1;
  unscoped/`--changed` still returns the placeholder. Tests `tests/test_engine_image_matrix.py` and
  `tests/test_check_engine_pins_published.py` lock the three behaviours incl. the `llama-cpp` replay.
  OpenSpec change `engine-selection-canonical`.
