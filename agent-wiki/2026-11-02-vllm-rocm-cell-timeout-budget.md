# 2026-11-02 vllm/rocm engine-build cell timeout raised 240 → 480 (issue #1568)

## What

`engine-build`'s `build` job had a single `timeout-minutes: 240` for every
engine × variant cell. The vllm/rocm cell produces its own CI proof for
`#1568`'s AMD index fix, and on two dead attempts it could not finish
`make build-engine` inside 240 minutes: the second (`41451995248`) ran 4h and
was terminated by the timeout while still on the ROCm compile (guard and matrix
legs were green; only the build cell died). The code was not the block — the
ROCm toolchain compile is simply heavier than the other cells, the same class
of capacity limit #1453 already documented for cuda, not a gate weakness.

## Change

`.github/workflows/engine-build.yml` now computes the cell budget per
engine × variant:

```yaml
timeout-minutes: ${{ (matrix.engine == 'vllm' && matrix.variant == 'rocm') && 480 || 240 }}
```

Only the vllm/rocm cell gets the 8h budget; every other engine and variant
keeps 240. No correctness check is reduced — this is a capacity ceiling for one
cell, not a changed test, skip, or weakened assert. The ROCm build steps are
untouched.

## Verification

- The workflow parses (repo `make lint` / YAML parse) with the expression as
  written; the expression is the GitHub `&& … || …` idiom returning the operand
  value — 480 for `(engine == 'vllm' && variant == 'rocm')`, 240 otherwise.
- Proof runs gate on the issue: boxes 5/6/9 of the vllm-rocm openspec change
  tick only on a COMPLETED/SUCCESS `engine-build` run at the PR head, run id and
  head sha named.
