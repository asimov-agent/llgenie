# mlx-plan-catalog-seam

## ADDED Requirements

### Requirement: The whole-repo pick plans resolve through the committed quant table first

When `data/trending-quant-catalog.json` lists the model+engine pair,
`plan_download(model, fmt="mlx-safetensors"|"safetensors")` SHALL return the table's
fitting plan (largest within the weight budget) — repo, revision, files and size as
recorded — and SHALL NOT resolve that pair against the live Hub. The live resolution in
`plan_download` SHALL remain the fallback only for models/engines not listed in the table.

#### Scenario: table wins over a diverged live recording

- **WHEN** the table records a fitting quant plan for the pair AND a live recording (or
  live Hub) reports the same repo as NOT fitting the budget
- **THEN** `plan_download` returns the table's plan, and `llgenie --pick --engine <eng> --dry`
  succeeds for that model+engine (the pick and the matrix answer through one decider)

#### Scenario: unlisted pair still resolves live

- **WHEN** the model+engine pair is not listed in the table (or the table is disabled via the
  `LLGENIE_QUANT_CATALOG=""` seam)
- **THEN** `plan_download` resolves against the live Hub exactly as before, and a fitting repo
  yields a plan

#### Scenario: nothing fits the budget in either seam

- **WHEN** the table's plans AND the live repos all exceed the weight budget
- **THEN** `plan_download` returns None and `offer()` names the no-fit reason — no plan is
  invented from a stale table entry

### Requirement: The seam decides divergence; the vendored pair stays as main shipped it

This change SHALL NOT rewrite `data/models.json` or `data/trending-quant-catalog.json`. A
table/Hub divergence is resolved by the seam — the table is the decider for catalogued pairs —
not by a resync inside the fix. Upstream store churn that removes tracked entries is its own
linked issue (#2722), gated by the additive-only `make check-registry`.

#### Scenario: the diverged lfm2.5 pair agrees through the seam

- **WHEN** the catalog records a fitting whole-repo MLX quant for `lfm2.5-24b-a2b` (DWQ-3bit,
  9.7876 GB) while the live repo was re-pushed beyond the 9.80 GB budget, as in the red
  ci-hf-live run
- **THEN** `offer()` and the CLI plan both answer from the table, and the network
  pick-agreement suite passes against main's vendored pair unchanged
