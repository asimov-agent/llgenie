# vllm-rocm-thin-prebuilt — tasks

- [x] rocm cell thin-prebuilt: `prebuilt: true`, `base: docker.io/rocm/vllm:<AMD-tag>`, `install: []`; `check-engine-params` 0 stale (on main via #2429)
- [x] add `("vllm","rocm")` to `NO_CACHE_EXPORT` in `scripts/engine_image.py` so pushless local verify builds route to the docker driver (measured footprint + run id)
- [x] docs trio per #1123: `agent-wiki/2026-11-08-vllm-rocm-thin.md` + `docs/changes.d/` fragment + regenerated `CHANGES.md`; `make check-docs` green
