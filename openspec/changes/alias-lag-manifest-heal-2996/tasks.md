# Tasks — alias-lag-manifest-heal-2996

## Implementation

- [x] Gate routes by gap class: `scripts/check_engine_pins_published.py` lag branch emits `[aliasmove] <engine> <variant> <tag-suffix> <pin-digest>` and no `[select]` for lag cells; `[select]` stays manifest-unknown-only.
- [x] New mover `scripts/engine_alias_move.py`: imagetools manifest move, post-move digest verification, contract refusal; joins "CI entrypoints" in `scripts/package-layers.json` with stated edges to `engine_image` and `proc`.
- [x] Make target `engine-alias-move` in `mk/engines.mk` (`ENGINE=`/`VARIANT=`/`SUFFIX=`/`DIGEST=`), wired for `make check-wiring`.
- [x] `.github/workflows/registry-liveness.yml`: `packages: write` permission; heal step before the fleet gate — publisher-in-flight deferral, `[aliasmove]` contract validation, GHCR login, per-cell `make engine-alias-move`.

## Tests

- [x] `tests/test_check_engine_pins_published.py`: lag scenarios demand `[aliasmove]` + no `[select]` (including the `vllm`/`cuda` DEFAULT_CPU_ONLY shape); manifest-unknown scenario keeps demanding `[select]`.
- [x] New `tests/test_engine_alias_move.py`: command shape (no build), post-move verify pass/fail, malformed contract refusal.
- [x] Workflow test pins the liveness heal step: `[aliasmove]` parse, `packages: write`, heal ordered before the fleet gate, publisher-in-flight skip.

## Verification (tick each with its replayable proof)

- [x] `make -s check-package-layers` exits 0 with `engine_alias_move` in "CI entrypoints".
- [x] `make -s check-workflows` exits 0 on the changed workflow.
- [x] `make -s check-wiring` exits 0 with `engine-alias-move` wired.
- [x] `make test-unit` exits 0 (full battery green at the lane head).
- [x] `make openspec-validate NAME=alias-lag-manifest-heal-2996` exits 0.
- [x] `make lane-preflight` prints `preflight: OK` at the final head.
