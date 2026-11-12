# registry-liveness-select-parse — proposal

Issue: [#2567](https://github.com/asimov-agent/llgenie/issues/2567)

## Why

On `main` `e6b9b4b4f`, the `registry-liveness` dispatch step parses its own `[select]`
contract lines with a 3-variable `while read -r engine variant tag`. The gate prints
**4** space-separated fields per missing cell — `[select] <engine> <variant> <tag-suffix>`
(`scripts/check_engine_pins_published.py:128`) — so every field shifted one slot right:
`$engine` became the literal `[select]`, `$variant` the engine id, `$tag`
`"<variant> <tag-suffix>"`. Measured on the run for `e6b9b4b4f` (job 131076815722): all 22
dispatch lines read `dispatching engine-build push=true for [select]/llama.cpp (missing
tag cpu 7d7f0287-1b5db7a2-cpu)`.

The dispatch is the repo's only self-heal for unpublished committed engine images
(issue #2259). With shifted fields, `engine-build` matched no committed params id for
`engine="[select]"`, synthesized its `none/none` placeholder, and the runs completed
"success" having built and published nothing — the exact failure mode #2561 documented
for nine runs on `aa700cf27`. The measured backlog (19 committed cells unpublished,
stable across 3 consecutive gate passes) never drains, every unit gate in the repo stays
red, and `registry-liveness` itself stays red.

## What Changes

- **`.github/workflows/registry-liveness.yml`** — the dispatch read loop gains the
  marker as its own field: `while read -r sel engine variant tag`, and any line whose
  first field is not exactly `[select]` is skipped loudly rather than dispatched with
  shifted fields. A line missing cell fields (short of 4 tokens) is also skipped loudly.
  The dispatch now forwards `engine=<committed id, dots intact>`, `arch=<variant>`,
  `push=true`, `tag=<suffix>`.
- **`tests/test_check_engine_pins_published.py`** — `test_the_liveness_dispatch_reads_all_four_select_fields`
  locks the workflow's read-loop field count and guard to the gate's 4-field `[select]`
  line, so the two cannot drift apart again.

## Not covered

- `engine-build` should red, not vacuously "succeed", when `inputs.engine` names no
  committed params id (the `none/none` placeholder hid this defect twice — 9 runs on
  `aa700cf27`, 22 here). Filed as #2568; that issue links back to #2567.

Refs: #2259 (the dispatch origin), #2561 (the preceding reverse-parse fix), #2567 (this
issue), #2568 (the deferred red-not-placeholder guard).
