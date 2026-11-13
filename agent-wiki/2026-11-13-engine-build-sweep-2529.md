# Engine × arch non-root sweep proof (issue #2529)

Date: 2026-11-13 · Issue: #2529 · Umbrella: #2504 · Engine non-root PR: #2517 · Docs PR: #2619

## What was verified against the spec

The umbrella #2504's engine half landed through #2517 (every shipped engine Dockerfile
now runs as uid/gid 1000). This note records the sweep proof measured on `main`
`da2fc5adb5d57a8dfb7498452c7892373c39bd01` (2026-11-13):

- **Pin/referee state.** `python3 scripts/check_engine_pins_published.py check --all`
  exits 0 with **all 28 committed engine cells published**; the resolver recomputes
  each cell's context hash from the CURRENT (non-root) Dockerfiles and the published
  tags match — proof the published tags are fresh post-#2517 contexts, not stale pre-edit
  tags.
- **Populations named.** The params matrix (`engine_image.matrix()`) lists 30 variants;
  4 of them are disabled variants absent by design —
  `exllamav3-rocm/rocm`, `llama.cpp-laurentzuijdwijk/cuda`, `llama.cpp-prism/cuda`,
  `llama.cpp-prism/rocm` — and `committed_cells()` (the gate denominator, 28) skips
  exactly those. Published roster (28) == committed pins (28); no orphan tags outside
  the committed set.
- **Non-root proof per tag.** `docker buildx imagetools inspect --format
  '{{json .Image.Config.User}}' <tag>` returns `"1000:1000"` for all 28 published tags,
  including both mlx cells.
- **Trivy misconfig half.** `make security-scan TOOL=trivy` on `main` `da2fc5adb` exits 0
  with **zero DS-0002 findings across every Dockerfile** (the containers/test/Dockerfile
  holdout closed via #2608); the only remaining dockerfile misconfig row is
  `containers/agent/Dockerfile` (':latest' tag rule, not DS-0002).
  `make security-issues-reconcile` exits 0 and posted clearing evidence to the 39
  `trivy-misconfig:DS-0002:*` per-file issues (e.g. #2397–#2401, #2405–#2428, #2464–#2467,
  #2576).
- **vllm-rocm remediation chain.** The last failing engine-build dispatch
  (run 43287527989, 2026-11-12T19:11Z) proved the non-root cutover defect on the
  intermediate context `3a4d82f5-db98981b-rocm`: `/opt/python/bin/vllm` → exit 126
  Permission denied + entrypoint detect `ModuleNotFoundError: No module named 'vllm'`.
  The current committed rocm context `3a4d82f5-d04739cb-rocm` is published and a
  verify-only CI dispatch ran on it (run **43361645161**, push=false) as the loud
  detect proof: **completed success 2026-11-13** — the non-root rocm image builds and
  its entrypoint detect answers, closing the last failing cell of the #2517 wave.
  Post-merge registry-liveness runs (03:03:55Z, 03:34:05Z, 03:37:48Z) all completed
  success and dispatched no unnecessary engine-builds; the first full main CI on
  `da2fc5adb` (run **43360241282**) completed success.

## Sweep table (28 committed cells, engine × arch × tag × runtime User)

engine | arch | published tag (`llgenie/<engine>:<pin>-<context>-<arch>`) | image config User
---|---|---|---
| freetoken | rocm | `5a73685b-5049dcfd-rocm` | 1000:1000 |
| freetoken | cuda | `5a73685b-714cf864-cuda` | 1000:1000 |
| litert | cpu | `7a03724c-9659c97d-cpu` | 1000:1000 |
| llama-cpp-laurentzuijdwijk | rocm | `3c75be02-0ad6789f-rocm` | 1000:1000 |
| llama-cpp-laurentzuijdwijk | vulkan | `3c75be02-2107457c-vulkan` | 1000:1000 |
| llama-cpp-laurentzuijdwijk | cpu | `3c75be02-7a865fda-cpu` | 1000:1000 |
| llama-cpp-prism | cpu | `6447906b-4ba76449-cpu` | 1000:1000 |
| llama-cpp-prism | vulkan | `6447906b-f445abb9-vulkan` | 1000:1000 |
| llama-cpp | cpu | `7d7f0287-1b5db7a2-cpu` | 1000:1000 |
| llama-cpp | vulkan | `7d7f0287-221a5e64-vulkan` | 1000:1000 |
| llama-cpp | cuda | `7d7f0287-e536208a-cuda` | 1000:1000 |
| llama-cpp | rocm | `7d7f0287-eb9cea9a-rocm` | 1000:1000 |
| mlx | cuda | `93e6d4a6-a133ea69-cuda` | 1000:1000 |
| mlx | cpu | `93e6d4a6-e5ab3798-cpu` | 1000:1000 |
| ollama | rocm | `02480ca2-4848d275-rocm` | 1000:1000 |
| ollama | cuda | `02480ca2-4bfd2457-cuda` | 1000:1000 |
| ollama | vulkan | `02480ca2-4e6c3896-vulkan` | 1000:1000 |
| ollama | cpu | `02480ca2-d807b210-cpu` | 1000:1000 |
| sglang | cuda | `7df5dd09-7da30d41-cuda` | 1000:1000 |
| sglang | rocm | `7df5dd09-9c987c68-rocm` | 1000:1000 |
| strata | rocm | `4a416016-535290b9-rocm` | 1000:1000 |
| strata | cuda | `4a416016-f44ef553-cuda` | 1000:1000 |
| surogate | cuda | `ad6c0bbf-8b7a56b2-cuda` | 1000:1000 |
| tensorfold | cuda | `b392ffce-e7a55a20-cuda` | 1000:1000 |
| tensorrt-llm | cuda | `376f7e1b-1ecf7aa4-cuda` | 1000:1000 |
| vllm | cuda | `3a4d82f5-4c1f3eee-cuda` | 1000:1000 |
| vllm | cpu | `3a4d82f5-524f7326-cpu` | 1000:1000 |
| vllm | rocm | `3a4d82f5-d04739cb-rocm` | 1000:1000 |

## Current status

Umbrella #2504 and the test-image half #2518 are closed COMPLETED; this note closes the
evidence loop for #2529 (the issue carries the same table + replay commands).
