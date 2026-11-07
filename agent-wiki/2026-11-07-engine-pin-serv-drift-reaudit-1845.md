# Engine pin-validity + serving-drift re-audit at 23cb793c (engine-improver lane, own-domain, #1845)

Re-audit date: 2026-11-07. Measured head: `23cb793c` (origin/main at dispatch). Second bounded own-domain pass per #1245/#791 (engine-improver: engine-cell pin validity + serving drift). Measurement only; no code edits by this lane.

## Pin set enumerated (13 committed params files, containers/engines/params/*.json)

Same #1282-scan set as the a5b535c4 pass (unchanged pins across the `888e879a..23cb793c` lineage): exllamav3-rocm (`5226de53`, ref main), freetoken (`ba31db2e`, v0.2.1), litert (`771b06e1`, v0.19.0), llama.cpp (`1b6935b2`, master), llama.cpp-prism (`5628c733`, prism), llama.cpp-laurentzuijdwijk (`3c75be02`, perf/strix-vulkan), mlx (`93e6d4a6`, v0.32.2), ollama (`04088e7c`, v0.40.13), sglang (`7df5dd09`, v0.5.23), strata (`d94bac6a`, v0.2.9), tensorfold (`ef27f74f`, v1.2.1), tensorrt-llm (`376f7e1b`, v1.2.1), vllm (`3a4d82f5`, v0.33.0).

## Pin validity: 11/13 published sets resolve; 2 known-tracked 404 classes; exllamav3 not a gap

Probed with the repo's own exact-tag formula (`engine_image.resolve()`) and manifest digest (`_digest_http`), the same probe the publish gate uses:

- 11 engines' declared variants resolve published GHCR manifests: freetoken (cuda/rocm), litert (cpu), llama.cpp (cuda/rocm/vulkan/cpu), llama.cpp-prism (vulkan/cpu), llama.cpp-laurentzuijdwijk (rocm/vulkan/cpu), mlx (cuda/cpu), ollama (cuda/rocm/vulkan/cpu), sglang (cuda/rocm), strata (cuda/rocm), tensorrt-llm (cuda). Pins unchanged from a5b535c4 → no force-push/move drift.
- **tensorfold-cuda `ef27f74f` → HTTP 404** — the committed immutable tag is unpublished. Already filed as **#1846** (publish-gap) at the a5b535c4 pass; still OPEN. Re-confirmed, no duplicate filed.
- **vllm cuda+rocm `3a4d82f5` → HTTP 404** — only `3a4d82f5-*cpu` tags exist on GHCR (36 vllm tags). Root: rocm build reds (`exclude-dependencies` poetry backend, #1558) and the GPU cells die infra under the `--builder default` cold build (#1696), so `push-engine vllm` never publishes. Tracked at **#1684** (pin) and **#1558/#1696** (build). Gated until those land, not a new finding.
- **exllamav3-rocm `5226de53`** — `engine_image.resolve` errors cleanly ("no frozen params … metal-only, not servable") → the engine has no container image expected; NOT a publish gap.

No NEW resolvability finding beyond the two already-tracked classes.

## Serving drift: none measured

Declared serve params (launch flags/port/dtype/model id) in the 13 params files are byte-identical to the a5b535c4 baseline (verified diff of containers/engines/params/*.json across `888e879a..23cb793c` — no params change in that span). No engine's serving contract drifted from what the artifact the pipeline cites would serve.

## Result

`re-audited at 23cb793c, no new findings` (the only two 404 classes map to existing tracked issues #1846 and #1684→#1558/#1696; this lane does not implement them — routed to the normal queue).
