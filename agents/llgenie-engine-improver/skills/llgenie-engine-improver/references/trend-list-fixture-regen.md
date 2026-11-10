# Regenerating the derived trend-list matrix fixture

`tests/fixtures/trend-list-matrix.json` is DERIVED from `trend_list`/registry logic. After a branch
changes that logic the committed fixture is stale and
`test_trend_list_matrix::test_trend_list_matches_the_committed_matrix[...]` fails for many
(arch, vram, ram) cases at once (93, or 17 cuda cases when the arch-aware gate altered `trend_list`).

## Procedure

1. `make render-trend-list-matrix` — run ALONE, generous timeout.
2. `make check-trend-list-matrix` green.
3. Commit the regenerated fixture. Never hand-edit it.

## Pitfalls

- **Never read the mass of matrix failures as a product bug.** It is a stale derived fixture.
- **Verify the regen's SCOPE before committing a large diff.** Diff old vs new per case: every changed
  case must be the TARGET arch (0 non-target rows moved), the admitted model SET unchanged (0 models
  added/removed), and each changed row the expected mechanism (quote 2–3 before/after). A big diff
  (231+/231−) is legitimate when only target rows were re-picked; a diff that also moves a non-target
  arch row is unrelated drift — call it out, never sweep it in.
- **Timing:** render ~37 s + matrix test ~40–110 s. A single foreground command running
  stale-check + render + re-check exceeds the 180 s tool timeout MID-render, so the fixture is never
  written (`git status` empty) and it looks like the render produced no diff. Run the render alone,
  then the test alone.
- **Live-Hub dependency:** the render walks the Hub PER MODEL (`trend_rows` → `_hub_json`) and 429s HARD
  on a cold cache; the default `HUB_CACHE_TTL=3600` re-throttles it into a timeout that never writes
  the fixture. Set `LLGENIE_HUB_CACHE_TTL=86400` (day-long disk cache) so prior fetches persist and the
  render COMPLETES (`wrote 81 cases`); background it with notify when the Hub is cold. This live-Hub
  dependency IS the #1020/#1067 non-hermeticity — it hits the render, not just the tests.
- **A CANCELLED/queued/superseded unit run never surfaces this** — stale-fixture reds appear only in a
  COMPLETED `linux/unit`. A stream of cancelled unit runs at successive heads is NOT evidence the
  fixture matches; confirm with a local matrix run or a completed unit.
