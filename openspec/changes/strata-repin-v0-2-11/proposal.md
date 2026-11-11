# Re-pin strata to v0.2.11 — the newest all-variants-buildable Strata release

## Why

Strata's weekly engine bump (#2266) pinned v0.2.13@fb57f747, and the ROCm build
cell cannot link at that pin. Both failed engine-build runs (42950150623,
42956798213) stop at the same place:

```
ld.lld: error: undefined symbol: strata::prefill::fused::want_dm_f16(bool)
strata::prefill::fused::dm_f16_used()
ninja: build stopped
```

It is an upstream packaging bug, present at v0.2.12 too: the callers live in
`src/prefill/prefill.cpp` (v0.2.13 lines 4837/4849, always compiled) but the
definitions live in `src/prefill/moe_fused_iq.cu` (lines 2102-2103), a source
CMake adds only inside `strata_hip_mmq()`, which is gated by the `STRATA_PREFILL_MMQ`
option, **OFF by default** (`CMakeLists.txt` line 104, call site lines 423-424). The
call-site count in `prefill.cpp` is 0 for every release through v0.2.11 and becomes
1 at v0.2.12 and 2 at v0.2.13. Upstream knows — Niko1221/Strata#5473 is open and
unmerged — and v0.2.13 and v0.2.13.1 both carry the identical broken hip.cmake.

While the pin names v0.2.13, the bump PR can never satisfy its own acceptance
rule ("the engine's `make build-engine` cells for each committed variant build
and verify green at the new pin") because the rocm variant is committed and
cannot build, and `make check-engine-pins-published`
(`ghcr.io/asimov-agent/llgenie/strata:fb57f747-ad09193c-rocm` 404s) stays red.

## What Changes

- **`skills/engines/strata/SKILL.md`** — re-pin `ref`/`version`/`pinned` from
  v0.2.9@d94bac6a to v0.2.11@4a4160162e4a402e082f41aa0a88e6eed629d913, the newest
  release whose prefill.cpp has zero fused call sites (all-variants-buildable).
- **`containers/engines/params/strata.json` + `Dockerfile.cuda`/`.rocm`** —
  regenerated via `make generate-engine-params ENGINE=strata` so every frozen
  variant carries the new pin and the exact install steps Strata ships at v0.2.11.
- **`data/strata_models.json`** — re-synced via `make sync-strata-models` to
  Strata's setup.py at the new pin (adds the DeepSeek-V4.1-Flash-1017-GSQ-RCO-Coder
  family and the UD-IQ1_M quant, both present at v0.2.11).
- **Upstream-tracked deferral** — v0.2.13 is not abandoned; the deferred bump is
  tracked as upstream Niko1221/Strata#5473 and re-attempted when the link stubs
  land.

## Impact

- The strata bump lands green: both the cuda and the rocm cell build at v0.2.11,
  and `make check-engine-pins-published` resolves both GHCR tags.
- The weekly strata cadence resumes; the next bump stops printing the identical
  `want_dm_f16` link failure only when upstream #5473 ships.
- No second code path is added (the no-fallback rule): the rebuild is a pin move
  plus its generated artifacts, nothing else.
