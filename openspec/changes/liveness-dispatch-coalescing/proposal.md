# Change: registry-liveness coalesces a multi-cell dispatch wave into one sweep (#2579)

## Why

registry-liveness dispatches one engine-build run per `[select]` line. Measured on 2026-11-12:
8 dispatches at 1-second intervals (runs 43211663538…43211688780) queued in the
`engine-build-push` concurrency group behind a full-matrix run — building nothing useful and
displacing/delaying productive sweeps (the mechanism that killed sweep 43203422414 in #2570);
the same wave shape repeated after every main merge (663/664 pair, 666-671 pairs). Queued runs
occupy concurrency-group slots and runners for hours and force manual cancels to keep
publishing flowing.

## What Changes

- The dispatch step counts the gate's `[select]` contract lines. When MORE THAN ONE cell is
  missing, it dispatches ONE full-matrix `push=true` sweep (`gh workflow run engine-build.yml
  -f push=true` with no engine/arch inputs — engine-build's documented empty-input sweep
  builds every cell and each green job publishes its own tag).
- Per-cell dispatch (engine+arch+push=true from the named contract fields) stays for the
  exactly-one-missing-cell case, unchanged.
- The #2567 positional contract validation runs BEFORE any dispatch shape and still refuses
  malformed lines loudly.
- The fleet gate's `exit "$rc"` hard-fail and the tracking-issue step are untouched.

## Impact

- Affected code: `.github/workflows/registry-liveness.yml` (dispatch step only),
  `tests/test_check_engine_pins_published.py` (new lock), OpenSpec change, wiki + changes fragment.
- NOT affected: engine-build.yml (its sweep semantics already exist), the `[select]` gate
  contract, per-cell dispatch for the single-cell case, any other workflow.
