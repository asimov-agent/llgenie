# Live-HF probes move to the ci-hf-live seam (issue #1178)

The `check-registry` and `check-quant-catalog` Make steps are now hermetic within the
`ci-unit` gate: each replays a committed fixture (`tests/fixtures/readme-link-answers.json`,
`tests/fixtures/quant-catalog-hub-snapshot.json`) instead of issuing a live Hub GET per link or
regrowing every catalog cell. The live probes run only on the dedicated `ci-hf-live` pipeline,
which now also carries them at `LIVE=1`.

The live seam's twice-hourly `schedule` lands on minutes `25` and `57` — odd minutes GitHub
actually fires (issue #560 drops `:00`/`:30`), chosen because every lower odd pair is already
reserved by another bot's slot (issue #275). The debounce window is `<20` minutes so it never
swallows the next scheduled probe across the 28–32 minute `:25`/`:57` gap.
