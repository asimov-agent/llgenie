# Adding a backend to the index

The backend set is extensible (CUDA / Metal / CPU today; AMD/ROCm is the next
instance). A backend is threaded through many places that must change together —
a contract change without the tests in the same change goes red (rule 11).

## Design pattern: vendor-API backend vs cross-vendor engine

- **Backend enum value = the vendor's compute API** — CUDA = NVIDIA, Metal =
  Apple, ROCm = AMD. One value per vendor.
- **A cross-vendor API is NOT a backend** — it is an engine detail classified by
  the hardware it ran on. Vulkan runs on AMD AND NVIDIA, so a Vulkan measurement
  goes to the ROCm table when the hardware is AMD and the CUDA table when it is
  NVIDIA — exactly as `llama.cpp (PrismML fork)` is an engine today, not a
  backend. The engine name records the real runtime; the backend records the
  vendor hardware.

## The checklist (all must change together)

1. **`data/model_contract.json`** — two enums: `models[].backends[].enum` and
   `engines[].backend.enum` (add the new value + combined forms like
   `"CUDA / ROCm"`). Additive → edit in place, no version bump.
2. **`data/search_contract.json`** — `properties/backend.enum` (the raw-snapshot
   group name, e.g. `"amd"`) and `models[].backends[].enum`.
3. **`scripts/update_trending.py`** (renderer + classifier):
   - `SEARCH_GROUPS`: add a group of lightbrd queries for the new vendor.
   - a `_<VENDOR>_HW` keyword tuple + a branch in `measurement_backend()` placed
     BEFORE the CUDA default.
   - `BACKENDS` tuple + `BACKEND_TITLES` (distinct emoji + title).
   - `ENGINE_BACKEND`: single-backend engines for the new vendor; cross-vendor
     engines → `None` (classify by hardware).
   - `_CARD_VRAM`: add the vendor's consumer cards → VRAM so `hardware_vram_gb()`
     returns a real value (else the VRAM tier is unknown).
   - `_DATACENTER_HW`: add the vendor's datacenter parts so they never earn the
     speed bonus.
   - `render_readme()`: most-loved column + `backend_table()` + engine matrix +
     engine guide.
4. **`scripts/validate.py`** — `check_backend_sort` iteration,
   `check_readme_measurements` column map, `check_readme_engine_links`.
5. **`scripts/engine_registry.py`** — `_infer_backend()` must recognize the new
   value (AMD-only → `"ROCm"`, mixed → `"CUDA / ROCm"`).
6. **`Makefile`** — `_search-<vendor>` Hermes prompt + `search-<vendor>` target,
   wired into `search` and the refresh matrix; `scripts/smoke_search.py`
   `BACKEND=<vendor>`.
7. **`README.md`** — regenerate (never hand-edit).
8. **`data/models.json`** — add measurements + `backends[]` + `engines` registry
   entries.
9. **Tests** — update the per-file fixture helpers (`good_store` / `store` /
   `sample_store` / `cuda_table`) in the SAME change (rule 11).
10. **`AGENTS.md`** — update the backend list in the rules.

## Pitfalls

- A new vendor's measurement with no classification branch falls through to the
  CUDA default — the wrong table. Add the branch before the default.
- A cross-vendor API keyword (e.g. `"vulkan"`) alone is not enough to classify —
  require a vendor hardware token too, or a Vulkan-on-NVIDIA measurement lands
  in the wrong table.
- Never fabricate t/s for the new backend; a sparse backend stays thin (like
  CPU), never padded.
- Ground the "how others do it" section before writing the issue: search for the
  vendor's real inference paths (e.g. ROCm vs Vulkan for AMD) so the design
  decision is accurate, not guessed.
