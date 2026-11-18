# Tasks: pack-format-store-launch

Checklist of record. Each step maps to a spec requirement in
`openspec/changes/pack-format-store-launch/specs/pack-format/spec.md`. Ticked the moment
the work is verified with real tool output.

## Model store — manifest-driven pack fetch (scripts/hf_download.py)

- [x] 1.1 Add `_read_manifest(filename)` — an existing `.json` path names the pack file set
      (`{"files": [...]}` or a bare array); `_present_pack(dest, files)` is true only when
      EVERY named file is on disk. Non-manifest filenames keep today's behavior.
- [x] 1.2 `main()` fetches a pack manifest by driving every named file through the same
      single-file path (`fetch_one`), reporting `PACK COMPLETE N/N` only when all present;
      a partial set resumes, never passes as complete.
- [x] 1.3 Hermetic e2e tests (real fake-`hf` subprocess): every named file lands in one
      dir, a partial pack resumes, a bare-array manifest is accepted —
      `tests/test_hf_download_pack.py` (`make test-unit`).

## Model store — pack-aware planning, gating, download (scripts/model_engine_pick.py)

- [x] 2.1 `pack_manifest(model)` reads a `formats[]` entry's `files` list as a pack
      declaration (repo, revision, file set, entry); a model with no such entry returns
      None and is untouched.
- [x] 2.2 `pack_plan(model, budget)` plans the whole-directory download sized by the SUM of
      every file's bytes, refuses when any named file is missing on the Hub, and carries
      the declared `pack` layout.
- [x] 2.3 `download()` routes a pack dir plan through the existing single-file path back
      into the pack directory, and writes the engine config via `write_pack_config`.
- [x] 2.4 Hermetic tests lock plan/gate/download for the pack fixture —
      `tests/test_pack_format.py`.

## Whole-file-set card/VRAM gating

- [x] 3.1 `pack_weight_gb(model)` = the whole-file-set weight (summed per-file when the
      format entry states sizes); `stated_budget_gb` reads it first, so `fits` /
      `card_evidence` admit or refuse a pack as a set.
- [x] 3.2 `make check-vram-scope-view` stays green (the vendored registry file is
      unchanged; the view is a pure function of it). Verified real: `[vram-scope-view] OK`.

## Launch contract — pack-config seam

- [x] 4.1 `write_pack_config(model_dir, layout)` writes
      `<model_dir>/llgenie-pack-config.json` wiring each named part to its absolute path
      under the pack dir (absolute parts pass through); `download()` invokes it for a pack
      plan without letting a config-write failure fail the download.
- [x] 4.2 Hermetic test locks the config shape — `test_write_pack_config_*` in
      `tests/test_pack_format.py`.

## edge0 decision (measured reality)

- [x] 5.1 Re-measured on this main: `data/models.json` (118 rows), `unsupported-engines.json`,
      `trending-quant-catalog.json`, `strata_models.json` contain NO `edge0`/`Edge0`/`145b`
      reference; `make check-engine-skill-gap` reports `unresolved 0`, `shipped 17`,
      `known-unsupported 29`. The issue's claim that the vendored record carries
      `Edge0-145B` is FALSE on this main. There is therefore no `edge0` skill-gap to close
      and no date-stamped `edge0` decision to re-record today; the wiki entry names this
      measured absence and records that the landing capability is what revisits it. No
      fabricate-a-decision entry is written to `unsupported-engines.json` (that would be a
      stale decision for an engine the store does not list, which the gate rejects).

## Verification (final)

- [x] 7.1 `tests/test_hf_download_pack.py` + `tests/test_pack_format.py` pass (real pytest
      output, this host): 12 new tests green (3 real fake-`hf` pack-fetch + 9 unit /
      download-integration); the surrounding gates (`test_card_gate_measured_vram`,
      `test_vram_scope_filter`, `test_hf_download_stall`) stay green.
- [x] 7.2 `make check-vram-scope-view` green; `make check-engine-skill-gap` green
      (`unresolved 0`).
- [x] 7.3 `python3 -m py_compile` clean on `scripts/hf_download.py` and
      `scripts/model_engine_pick.py`.
