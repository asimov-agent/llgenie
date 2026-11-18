# Pack-format store + launch path (issue #2909)

## What was measured

Issue #2909 asked for a pack-format path through llgenie's model store and launch
contract: manifest-driven multi-file fetches, card/VRAM gating sized by the whole file set,
and `MODEL=` resolving to a pack directory whose named parts are wired into one engine
config — the capability `edge0-145b` (engine `edge0`, upstream 2026-11-17) needs.

On this main (`f7eb17d028da213fad321915be62cec485e19eb7`, `make bot-preflight`), the
issue's specific data premise did **not** hold: `data/models.json` (118 rows),
`data/unsupported-engines.json`, `data/trending-quant-catalog.json` and
`data/strata_models.json` contain **no** `edge0` / `Edge0` / `145b` reference (grep and
json-count both 0), and `make check-engine-skill-gap` reports `unresolved 0`, `shipped 17`,
`known-unsupported 29`. So there is no `edge0` registry row to ship a skill for and no
date-stamped `edge0` decision to re-record in `unsupported-engines.json` today — the engine
is simply not in the vendored store yet. The generalized pack-format capability was still
actionable and testable, so it shipped; this entry records the measured absence so a future
`registry-sync` that adds `edge0` revisits it (`check-engine-skill-gap` will then name it).

## The fix (OpenSpec change pack-format-store-launch)

1. **`scripts/hf_download.py` — manifest-driven pack fetch.** A `<filename>` that is an
   existing `.json` path names the checkpoint file set (`{"files": [...]}` or a bare
   array). Every named file is fetched into ONE destination directory through the same
   single-file path (resume, stall-watch, 429-wait, retry, refresh); a pack is "present"
   only when EVERY named file is on disk, and a partial set resumes instead of passing as
   complete. Same CLI, no second downloader.
2. **`scripts/model_engine_pick.py` — pack-aware planning, gating, launch.** A `formats[]`
   entry carrying a `files` list is a pack (`pack_manifest`); `pack_plan` plans it as a
   whole-directory download sized by the SUM of its files and refuses a set any of which is
   missing on the Hub; `pack_weight_gb` feeds `stated_budget_gb` so the card gate admits or
   refuses a pack as a set; `download()` routes a pack dir plan back into the directory and
   writes the engine config via `write_pack_config` (named parts → absolute paths in
   `<model_dir>/llgenie-pack-config.json`).

## Verified against the spec

- `tests/test_hf_download_pack.py` (real fake-`hf` subprocess, no mocks) — whole-set fetch
  into one dir, partial-resume, bare-array manifest: 3 green.
- `tests/test_pack_format.py` — manifest read, whole-set size gating, missing-file refusal,
  plan_download routing, whole-set card-gate weight, launch config writer, and the
  download() integration that writes the config into the pack dir: 9 green.
- Gates green: `make check-vram-scope-view` (`OK`), `make check-engine-skill-gap`
  (`unresolved 0`), `python3 -m py_compile` clean on both modules. `make test-unit` of the
  touched neighbours (card gate, vram filter, stall, download) all green.

## Not covered / deferred

- **`make test-engine-host` serve proof on a pack-format model** — needs a real pack-format
  checkpoint on a real GPU and a shipping `edge0` engine image, neither of which exists in
  this repo/host. Both are explicitly "Not covered" in issue #2909.
- **The `edge0` decision revisit (sub-path of the issue's acceptance)** — the engine is not
  in the vendored registry, so `make check-engine-skill-gap` is already green with
  `unresolved 0`. It becomes actionable when `registry-sync` lands `edge0`; that is what
  issue #2903 (the unskilled-engine tracking issue this change was filed from) carries.

## Current status

The pack-format capability ships (store fetch + whole-file-set gating + launch-config
seam), hermetically proven. The edge0-specific halves stay deferred to the measured
registry reality (tracked by #2903).
