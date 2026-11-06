# Engine pin-validity + serving-drift audit at a5b535c4 (engine-improver lane, own-domain, #1845)

Audit date: 2026-11-06. Measured head: `a5b535c4` (origin/main at dispatch). Bounded own-domain audit per #1245/#791 (engine-improver: engine-cell pin validity + serving drift). Measurement only; no code edits by this lane.

## Pin set enumerated (13 committed params files, containers/engines/params/*.json)

The #1282-scan set: exllamav3-rocm (`5226de53`, ref main), freetoken (`ba31db2e`, v0.2.1), litert (`771b06e1`, v0.19.0), llama.cpp (`1b6935b2`, master), llama.cpp-prism (`5628c733`, prism), llama.cpp-laurentzuijdwijk (`3c75be02`, perf/strix-vulkan), mlx (`93e6d4a6`, v0.32.2), ollama (`04088e7c`, v0.40.13), sglang (`7df5dd09`, v0.5.23), strata (`d94bac6a`, v0.2.9), tensorfold (`ef27f74f`, v1.2.1), tensorrt-llm (`376f7e1b`, v1.2.1), vllm (`3a4d82f5`, v0.33.0).

## Pin validity: 13/13 PASS

- Every registry ref resolves via `git ls-remote`; every pinned sha is present and is an ancestor of (or equals) its ref's commit. No force-pushed/moved pins; no 422 annotated-tag-object false negatives (tag-object pins vllm/sglang/strata/tensorfold/tensorrt-llm verified satisfiable via `ls-remote` peeled commits).
- litert `v0.19.0` tag was re-pointed to `83ce6067` past its pin `771b06e1`, but the pin stays an ancestor → still resolvable; **note only, not a finding**.
- All 6 distinct base images resolve in their registries (`docker manifest inspect`): nvidia/cuda:13.0.2, rocm/dev-ubuntu-24.04:7.0-complete, rocm/pytorch:…2.10.0 (digest-pinned `sha256:4449f856…`, manifest digest matches committed exactly → no new-source-into-old-base drift), lmsysorg/sglang:v0.5.23, nvcr.io/nvidia/tensorrt-llm/release:1.2.1, ubuntu:24.04.
- Install strings satisfiable by the resolver each cell uses (uv/pip/Zig); llgenie test-image flags (version/help, port=11434, model=llm-local) valid for the pinned CLIs per `binaries.json`.

## Serving drift: 1 finding, 10 clean, 1 expected-disable

- **Clean (11 published engines serve current committed params, immutable tags PUBLISHED in GHCR):** freetoken, litert, llama.cpp, llama.cpp-prism, llama.cpp-laurentzuijdwijk, mlx, ollama, sglang, strata, tensorrt-llm, vllm.
- **Expected-disable:** exllamav3-rocm (DISABLED in `engine_image.py` #103 cell) — no published image expected. Not a finding.
- **Finding — tensorfold publish-gap (#1846):** committed params tag `ghcr.io/asimov-agent/llgenie/tensorfold:ef27f74f-ab048303-cuda` (what `make install` pulls) returns **404** from GHCR (docker `manifest inspect` rc=1 ×3 with backoff + registry HTTP HEAD), while moving `:cuda`/`:latest` exist at stale digest `sha256:4a88deda…`. Publish predates bump PR #1519 (commit `768b59ec`); last main engine-build sweep (run `42175202425`) concluded FAILURE. Pin itself is valid upstream — class = publish-gap (#1365), not pin-missing. Filed as **#1846**, six-section, labels `continuous-improvement`+`agent:refined`, routed to the normal queue — never this lane's own pass.
- **Recurrence acknowledged:** #1846 cross-references security-lane audit **#1652** (2026-11-03, head `75f85118`), which already listed `tensorfold:ef27f74f-ab048303-cuda` → HTTP 404; the tag is still missing at `a5b535c4`, so the #1652 route has not produced a publish. Same cell, re-confirmed.

## Result

One filed finding (#1846 = recurrence of #1652's tensorfold cell); pin validity 13/13; every other published engine + base verified clean. The fix (re-publish the narrow `tensorfold × cuda` cell at the `ef27f74f` head with `push=true`, then `scripts/ghcr_publish_probe.sh` → `PUBLISHED`) routes to the implement queue through #1846 — not implemented by this audit lane. Full evidence in the audit record posted on #1845 (comment `6682737198`).
