# engine-smoke-documented-flags — proposal

Issue: [#2573](https://github.com/asimov-agent/llgenie/issues/2573)

## Why

Fleet run #645 (engine-build.yml run 43206254966, main `e6b9b4b4f`) failed `engine-build-mlx-cpu`
(job 131144134691): the binary smoke answered `-h` but `--version` exited 2, because
`mlx_lm.server` is argparse with no `--version` flag. `scripts/engine_smoke.py` pins the probe set to
EXACTLY `["-h", "--version"]` on both binary-smoke paths (image path ~line 205 citing issue #2319,
host skill path ~line 222) and consults the committed generated manifest only for the `probe: device`
skip. It never probes what the engine's own binary documents — even though the manifest the image was
generated from (`containers/engines/binaries.json`) already records the documented set per variant
(`mlx/cpu → flags ["--help"], probe "help"`, sglang cuda/rocm `["--help"]`, `litert/cpu ["--help"]`,
`tensorfold/cuda ["--version"] probe "version"`), the push gate has read it since issue #204
(`engine_image.variant_flags`), and the skill parser exposes it (`engine_skills.documented_flags`).
The gate's own contract (issue #1717) is "the binary answering the flags **it documents**", yet the
pinned pair bets every binary tolerates an undocumented `--version`. Measured at head `151c910ae`
(`ALL=1 make check-engine-pins-published`, make rc=2): 28 committed pinned cells, 21 published,
7 unpublished (`llama-cpp-laurentzuijdwijk/rocm`, `llama.cpp/cuda`, `llama.cpp/rocm`, `mlx/cpu`,
`tensorfold/cuda`, `vllm/cuda`, `vllm/rocm`). The collision is proven to red-block exactly one of
them: `engine-build-mlx-cpu` (run #645 job 131144134691 FAIL, `--version: binary exited 2`).
`sglang cuda/rocm` and `litert/cpu` (manifest-documented `["--help"]` only) publish today only
because their binaries empirically tolerate the undocumented `--version` — mlx is the measured proof
that binaries without it exist, and any future re-pin onto one reds such a cell permanently.

## What Changes

- `scripts/engine_smoke.py` `binary_smoke` image path: probe the generated manifest's documented
  flags via `engine_image.variant_flags(spec)` instead of the hardcoded pair; `probe: device` stays
  skipped exactly as today.
- `scripts/engine_smoke.py` `binary_smoke` host skill path: probe `engine_skills.documented_flags(skill,
  backend)` for the backend being smoked (per-backend map semantics honored).
- Vocabulary guard, fail-closed: any documented flag outside `{-h, --help, --version}` names the
  engine/variant and exits 1 — the #2319 ceiling (never probe more than the version/help family) is
  kept as a bound, not as a fixed probe set.
- Fallback preserved: when the manifest (or skill) documents NO flags, the probe set defaults to the
  pinned `["-h", "--version"]`, so #2319's behavior is unchanged for engines that document nothing.
- New hermetic test module `tests/test_engine_smoke_binary_flags.py` pins the per-variant probe sets
  (mlx → `--help` only; a both-flag engine → both; empty → the pinned default; device → skip; a
  vocabulary violation → fail closed), no docker and no engine builds.

## Benefit

The manifest stops being decorative: what a skill documents is exactly what CI tests, the gate's
"flags it documents" contract becomes literally true in code, and `engine-build-mlx-cpu` — the
measured blocked cell — becomes publishable in the next push wave with no engine-side hack. Cells
documenting `["--help"]` (sglang cuda/rocm, litert cpu) stop depending on undocumented `--version`
tolerance that has never been part of their contract; the remaining unpublished cells are waiting
on build time, not on a gate collision.
