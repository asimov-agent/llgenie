# registry-liveness-dispatch-shift

## Why

The gate prints four-token contract lines — `[select] <engine> <variant> <tag-suffix>`
(`scripts/check_engine_pins_published.py`) — but the registry-liveness dispatch loop reads
THREE variables from them, so every field shifts one slot right: `$engine` becomes the literal
`[select]`, `$variant` becomes the engine id, `$tag` swallows the variant. Measured on main
`e6b9b4b4f` (registry-liveness run 43187080395, job 131076815722): all 22 dispatch lines read
`dispatching engine-build push=true for [select]/llama.cpp (missing tag cpu 7d7f0287-…)` and the
22 dispatched runs (`43187181181`…`43187252711`) started with `engine="[select]"`, matched no
committed params id, synthesized engine-build's `none/none` placeholder, and "succeeded"
publishing nothing — the same vacuous-success class #2561 documented for nine runs on
`aa700cf27`. The self-heal for the unpublished-pin backlog (#2259) is therefore silently dead,
and every unit gate in the repo stays red on that backlog (issue #2567).

## What Changes

- The dispatch loop binds the contract positionally: `while read -r sel engine variant tag extra`,
  with the line accepted only when `sel` is exactly `[select]`, `engine`/`variant`/`tag` are
  non-empty, and `extra` is empty. A violating line is printed, counted, and fails the step —
  it is never dispatched.
- A test locks the workflow's read fields to the gate's line contract, so the two cannot drift
  apart again (issue #2568 files the complementary producer-side guard: engine-build must red on
  an unknown non-empty `engine` input rather than succeed vacuously).

## Impact

- Affected spec: `registry-liveness-dispatch-shift` (new capability).
- Affected code: `.github/workflows/registry-liveness.yml` (dispatch loop only),
  `tests/test_check_engine_pins_published.py` (one new contract test).
- Unchanged: the gate script, the `ALL=1` hard-fail, `--ref main`, `push=true`, and the
  dispatch's existing dedupe/idempotence behavior.
