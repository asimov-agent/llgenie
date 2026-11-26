# Alias heal now covers the canonical engine's `:latest` tag (#3080)

**Issue:** #3080 · **Branch:** `fix/3080-alias-move-latest`

## What changed

`make engine-alias-move` healed only a lagging `:<variant>` alias. The full-fleet pin gate
(#3003/#2988) also holds every engine's `:latest` to its canonical variant's committed pin, so
registry-liveness healed the variant half and re-redded on `:latest` on every re-probe (six
`ALIAS LAG` lines, `fleet_rc=2`, run `45773544133` at main `3cea715e3`).

`scripts/engine_alias_move.py` now repeats the byte-preserving manifest move to `:latest`
**only** when the lagging cell is the engine's canonical variant, using the same
`engine_image.engine_latest_variant` ownership rule the gate and publisher use. The same fetched
bytes and mediaType go to both tags, each verified at the pin digest through the same probe.
Non-canonical variants stay variant-only; the four-field contract and refusal rails are unchanged.

## What was verified

- `tests/test_engine_alias_move.py`: canonical moves both tags byte-for-byte (mlx/cpu and the
  measured tensorfold/cuda lag), non-canonical moves variant-only (vllm/cuda), a failed variant
  verify or a refused `:latest` PUT publishes nothing further — 19 passed, 0 skipped.
- Gate seam: the gate's single deduped `[aliasmove]` line now feeds a heal that covers both aliases.
- No engine build or run; the proof uses the fake `run`/`probe`/`put` registry seam.

## Anything left open

- The live heal of the six GHCR tags and the registry-liveness main-run green read (issue #3080
  AC-2/AC-3) land post-merge through the normal landing flow.
