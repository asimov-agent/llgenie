# 2026-11-21 — alias-lag manifest heal (issue #2996)

OpenSpec change: `alias-lag-manifest-heal-2996`. Issue: [#2996](https://github.com/asimov-agent/llgenie/issues/2996) (fixes the false repair premise recorded on #2989, gate half landed earlier via #2987).

## What was verified against the spec

- Gap-class routing measured in `scripts/check_engine_pins_published.py`: a resolved pin whose `:<variant>` alias digest lags now prints `ALIAS LAG` + `[aliasmove] <engine> <variant> <tag-suffix> <pin-digest>` and NO `[select]`; `[select]` is reserved for manifest-unknown cells. The `if lagged:` FAIL summary names the manifest move, not a build dispatch.
- New mover `scripts/engine_alias_move.py` (`make engine-alias-move`, `ENGINE=`/`VARIANT=`/`SUFFIX=`/`DIGEST=`): `docker buildx imagetools create -t <repo>:<variant> <repo>@<digest>` — a registry-side manifest re-point that builds nothing — verified by re-resolving the alias through `engine_image._digest_http` (the may-arm's own probe); malformed contracts (missing field, non-`sha256:<64hex>` digest, suffix contradicting `engine_image.resolve`) are refused at exit 2 with zero registry calls. Registered in "CI entrypoints" with stated edges to `engine_image` and `proc`.
- `registry-liveness.yml` heals BEFORE the fleet gate: probe → validate each `[aliasmove]` line → GHCR login with the job token (engine-build.yml's pattern, #1843) → per-cell `make engine-alias-move`; skipped while a same-head publisher is in flight (#2592); new `packages: write` scope documented as the same-repo manifest-move authority, not an expansion of engine-build's push scope. The `push=true` dispatch step keeps serving `[select]` (manifest-unknown) cells only.
- Measured why builds could never heal this class: `DEFAULT_CPU_ONLY = {"vllm"}` (`scripts/engine_image.py`) excludes vllm GPU variants from every matrix/sweep; red runs 44865940908 / 44879637744 / 44882516581 carried byte-identical `vllm:cuda`/`vllm:rocm` digests across green sweeps 44868119305 / 44881159100 / 44884434390.

## Key decisions

- Heal in-lane in `registry-liveness.yml` rather than teaching `engine-build.yml` a heal mode: the lag class needs no GPU and no build at all.
- `make engine-alias-move` target added to `mk/engines.mk` + `Makefile` (workflows must not call scripts directly).

## Current status

Gates green locally: `check-package-layers` (186 modules, 77 stated edges, 0 cycles), `check-wiring`, `check-workflows`, `openspec-validate`, targeted battery `tests/test_engine_alias_move.py` + `tests/test_check_engine_pins_published.py` + `tests/test_package_layers.py` = 65 passed. Full `make test-unit` and lane-preflight tracked in `tasks.md`.
