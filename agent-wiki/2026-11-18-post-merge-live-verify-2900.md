# 2026-11-18 — post-merge live verification landing read (#2900)

## What was verified

`ci-hf-live` had reddened on five consecutive `main` runs (44212692903, 44206920194,
44195647662, 44176093280, 44142734842) while `registry-liveness` stayed green: the committed
trend matrix pinned `LFM2.5-24B-A2B` at "smallest GGUF is 13 GB" for the four
`metal/16/{8,32,60,64}` cells, and the live trending build reported 9 GB. The collected data
had not been re-pinned since the 2026-11-15 vendored sync — the repo had no mechanism that made
a landing READ those batteries, so the drift was invisible until a scheduled run tripped.

The fix lane: `make -s sync-registry` (models 118 → 120, additive, `check-registry` green) →
`sync-quant-catalog` → `render-trend-list-matrix` (81 cells re-pinned) → `render-engine-skill-gap`
→ `skills-validate` (17 skills, 0 errors) → `check-trend-list-matrix` green. The new trending
carried four unskilled engines; `make -s spawn-engine-skill-issues` filed #2902 (basalt),
#2903 (edge0), #2904 (qwen-warp), #2905 (smolmaxxing), and dated decisions were recorded in
`data/unsupported-engines.json` in the same breath (deferred for the three servable CUDA-class
engines; not-shipped for the Metal-only llama.cpp kernel fork), re-rendering `engine-skill-gap`
to unresolved 0.

The durable mechanism: `make post-merge-live-check` (scripts/post_merge_live_check.py, CI
entrypoints layer) prints one verdict line per battery (newest completed main run id, event,
conclusion) plus the `check-trend-list-matrix` fingerprint line; exit 1 when any battery is
non-`success` on `main` or the fingerprint drifted, exit 2 when the `gh` stream cannot be read,
never a silent zero. `AGENTS.md` gained the `## Post-merge live verification (MANDATORY,
durable)` section; `tests/test_post_merge_live_check.py::test_the_landing_duty_is_recorded_in_agents_md`
is the box that keeps the duty named.

## Key decisions

- The gh seam is a GET with the query in the URL (a `-f` makes gh POST, and POSTing the
  runs-list endpoint 404s); the LIST endpoint names its fields `id`/`event`, not `run_id`/
  `event_name` — both measured live before committing.
- The card-ranking test's store-order inequality was replaced with reversal invariance after
  the re-pin made the global store order coincide with the 8 GB tier ranking (the old guard
  tested today's data, not the code; the shuffle test next to it already proved file-order
  independence).
- The mid-window staleness alarm (compare the committed matrix against a fresh trending read
  between syncs) is issue #2901, deliberately not implemented in this lane.

## Current status

Landing read proven at this lane's head; batteries green in CI remains the next proof the
landing itself carries. #2900 closes with the PR; #2901–#2905 stay open as linked work items.
