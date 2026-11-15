# 2026-11-15 — MLX plan seam reads the committed quant table (issue #2719)

## What was verified

- The red is real and measured on `main` `1dcbf4c3ae` (run 43736480220, the ci-hf-live `make
  test-unit-network` lane): for `lfm2.5-24b-a2b::MLX::metal`, `matrix()` proposes the cell from the
  committed quant table (hermitdave `LFM2.5-24B-A2B-MLX-DWQ-3bit` at 9.7876 GB, fits the 9.80 GB
  24 GB-metal budget) while `llgenie --pick --engine MLX --dry` refuses because `plan_download()`
  resolved MLX repos against the LIVE Hub, where the repo has since been re-pushed to 9.8835 GB
  (9.8667 GB safetensors) — no MLX repo fits.
- Fix: `plan_download`'s mlx-safetensors/safetensors branch now reads the committed HF class table
  via a new `_catalog_format_plans` helper when the (model, engine) pair is listed, serving the SAME
  budget-fitting snapshot `engine_supported_quants`/`_matrix_plan` serve — so `llgenie --pick` and
  `matrix()` answer the same question through the same seam. Selection is budget-first then
  largest-fitting (mirroring `_add`), so the two surfaces agree even if the table carries a duplicate
  plan size. A pair absent from the table still resolves live (fallback kept).
- Proof: redirected reproduction against the real Hub — pre-fix `matrix` offered 9.7876 GB /
  `plan_download`(live) returned None (disagree, the red); post-fix both serve the same 9.7876 GB
  plan (agree). `tests/test_pick_quant_catalog.py` (3 hermetic tests) passes and fails red on the
  reverted seam.
- Hermetic gates: `lint_linefeeds OK`, `check-wiring OK`, `check-quant-catalog OK` (generator output
  unchanged), `check-docs OK`.

## Decisions

- The AC3 resync (`make sync-quant-catalog`) was attempted against the live Hub but surfaced a
  generator defect: `carry_over` re-inserts a re-pushed repo at a STALE size beside its fresh live
  size (duplicate same-repo plans), and the diff is ~34k lines. Deferred as a separate issue so this
  change stays one objective (the durable code seam makes `matrix()` and `plan_download` agree
  regardless of table content; the weekly sync refreshes the table).
- The AC3/AC4 live verification (`make sync-quant-catalog`/`check-quant-catalog` and
  `make test-unit-network`) is exactly what the ci-hf-live lane runs on the real Hub after merge; the
  hermetic halves (AC1/AC2) are proven here.

## Current status

- Green and ready for the implement PR. OpenSpec change `fix-mlx-quant-catalog-seam`, all tasks
  ticked, `openspec-validate` (container) and `test-unit` (container) cannot be exercised in this
  environment (no Docker daemon) and are the job's/CI's gates.

Issue: #2719 (and the deferred generator-sync finding it opens)
