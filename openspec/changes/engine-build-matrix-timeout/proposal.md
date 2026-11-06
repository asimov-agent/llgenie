# engine-build-matrix-timeout — proposal

Issue: [#1818](https://github.com/asimov-agent/llgenie/issues/1818)

## Why

`engine-build.yml`'s build job carries a flat `timeout-minutes: 240` on every
matrix cell. The heavy vllm/rocm cell repeatedly hits that wall and is
**cancelled** at the cap while still compiling — reading `cancelled`, never a
verdict. Measured (issue #1818): 13 cancelled `engine-build-vllm-rocm` jobs,
five killed at exactly the 241m wall, while the same cell's completed-success
band is p50 ~59m / max ~107m. A hard cap that the target cell now trips
converts a slow-but-legitimate build into a silently-UNTESTED result instead of
a verdict, and cheap cells do not need the headroom.

## What Changes

- **`.github/workflows/engine-build.yml`**: the build job's `timeout-minutes`
  becomes matrix-aware by variant:
  `${{ (matrix.variant == 'rocm') && 360 || 240 }}` — rocm cells ~360,
  every other variant 240.
- **`tests/test_ci_variant_matrix.py`**: a regression test asserts the build
  job's timeout is the matrix-aware expression and reds on a flat value.
- Change-note trio: `agent-wiki/2026-11-06-engine-build-matrix-timeout.md` +
  `docs/changes.d/2026-11-06-engine-build-matrix-timeout.md` + regenerated
  `CHANGES.md` (per #1123).

Capacity only: `ci-verdict`, `ci-scope`, `make build-engine` untouched. Re-lands
the owner-authored intent from closed-unmerged PR #1609 at the current #1818
ruling (360, not 480).

## Benefit

Heavy GPU/rocm cells finish and produce a real verdict instead of being silently
killed at the wall; cheap cells keep a tight fast-fail budget; #1694 criterion 1
gets its tracked work item and #1696 a linkable target.
