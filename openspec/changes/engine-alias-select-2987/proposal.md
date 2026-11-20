# Make the committed pin gate alias-aware so merged pins get their arch tags moved (issue #2987)

## Why

Three committed engine cells serve stale `:<variant>` aliases on GHCR while `main` pins newer tags: at `a4afb185e` a digest sweep of all 29 committed cells shows `edge0:cuda` on `4a7964de-16ec5d83-cuda` (committed `4a7964de-874f7c96-cuda`, moved by the edge0 pack-format merge `c564764c5`), `vllm:cuda` on `0c57b419-4d7140a3-cuda` (committed `3a4d82f5-4c1f3eee-cuda`), and `vllm:rocm` on `0c57b419-a7edd5e8-rocm` (committed `3a4d82f5-d04739cb-rocm`). Issue #178's contract is "publish the unique tag on the PR; **move the arch tag and retest it on main**" — but the on-main mover is registry-liveness's `[select]`-driven `engine-build.yml` dispatch (`push=true`, `moving_tags` default `true`), and liveness dispatches only cells the gate reports. `scripts/check_engine_pins_published.py` resolves only each cell's exact pin tag: once a PR-scoped producer (moving_tags=false, #178) publishes the unique tag, the committed manifest always resolves, so a merged pin bump or content re-derivation never selects the cell again. The gate is green and today's liveness runs (three daily crons + every main push) never move the aliases; alias-following consumers run builds `main` does not pin, invisibly.

## What Changes

- `scripts/check_engine_pins_published.py::_probe` gains an `alias_check` mode: for every cell whose committed tag resolves, also resolve the cell's `:<variant>` alias manifest and compare digests. Aligned prints `[pins] ALIAS OK <ref>`; a lagging or absent alias prints `[pins] ALIAS LAG <alias-ref> (<alias digest> != <pin digest> | absent)` plus the same `[select] <engine> <variant> <tag-suffix>` dispatch-contract line (#2561/#2567) and reds the check. The repin-diff PR-lane path (`check`) never turns it on.
- `check_committed` reads the knob from `ENGINE_PINS_ALIAS` when no explicit value is passed (same shape as `ENGINE_PINS_PATIENCE_SECONDS`, #2973): `1`/`true` on, unset/`0`/`false` off, a garbage value WARNs on stderr and stays off. Knob off, the check probes exactly once per cell — today's tag-existence semantics, unchanged for every PR lane and `ci-hf-live`.
- `.github/workflows/registry-liveness.yml` sets `ENGINE_PINS_ALIAS: "1"` on its two `make check-engine-pins-published ALL=1` invocations (the fleet gate and the dispatch gate), so a lag selects the cell and rides the existing #2579 coalesced `push=true` sweep, which moves `:<arch>`/`:latest` and retests the published leg. liveness triggers on every main push plus three daily crons, so a merged pin is realigned within minutes, and a realignment that failed to move the alias becomes a red gate with named cells instead of a silently stale fleet.
- Fixture tests (hermetic, injected digest probes): aligned → green with `ALIAS OK`; lag → red with `ALIAS LAG` + `[select]`; absent alias → same red; knob unset → one probe per cell, mismatched alias stays green (PR-lane strictness unchanged); knob via env; malformed knob loud and off. A workflow test pins the env wiring on both liveness invocations.

## Impact

- `scripts/check_engine_pins_published.py` — `_probe` (new `alias_check` param, per-cell alias digest comparison), `check_committed` (new knob read). `check()` and `report()` unchanged.
- `.github/workflows/registry-liveness.yml` — `ENGINE_PINS_ALIAS: "1"` on the two gate steps; the dispatch machinery is untouched (it already turns `[select]` lines into `gh workflow run engine-build.yml -f push=true`).
- `tests/test_check_engine_pins_published.py` — new hermetic cases + workflow wiring test in place.
- No host-side GHCR push and no dispatch is run by this change: the three lagging cells are repaired by the next registry-liveness push/cron run of the merged tip (GitHub event, per the CI-pipeline discipline rule).
- Not covered (separate issues, linked both ways): #2988 digest comparison for the engine-level `:latest` alias; #2989 post-merge landing verification that the liveness dispatch realigns `edge0:cuda`, `vllm:cuda`, `vllm:rocm` and the knobbed live sweep reads 29/29 green.

Refs: issue #2987 (Problem/Why/fix/AC with the measured digests), side issues #2988, #2989.
