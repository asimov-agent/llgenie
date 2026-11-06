# engine-build cell timeout is tiny by matrix (rocm ~360 / other 240)

## Background

`#1696` (`ea0b9033`) landed the matrix-aware build-cell timeout at
`.github/workflows/engine-build.yml:168`:

```yaml
timeout-minutes: ${{ (matrix.variant == 'rocm') && 360 || 240 }}
```

This supersedes the earlier `#1568` note that documented the **240 → 480**
vllm/rocm-only fold. The shipped value at the head is **360 for rocm cells /
240 for every other variant** — not 480. This note is the correction #1694
AC4 names: the AC4 change-note files must exist and document the value that is
actually in the workflow at the PR head, verbatim.

## The fold, as written

`${{ (matrix.variant == 'rocm') && 360 || 240 }}` evaluates to:

- **rocm** cells (the heavy GPU/rocm build class): **360 minutes** — ~3.4× the
  measured completed-success max (~107m, p50 ~59m), sized from the band, not by
  feel; a genuine slow ROCm compile can finish instead of being cancelled on
  the old 240 wall.
- **cuda / cpu / vulkan** cells: **240 minutes**, unchanged — a hung cheap cell
  still fails fast.

This is capacity only: no `ci-verdict`/`ci-scope` gate is touched and no
`make build-engine` step is weakened. It adopts the #1818/#1820 ruling (~360,
the merge that landed on main `24b97d50`) for the timeout that #1696 carries.

## Verification

- The workflow file at the PR head (`#1696` `ea0b9033`) contains exactly
  `timeout-minutes: ${{ (matrix.variant == 'rocm') && 360 || 240 }}` (line 168).
- `make check-docs` green with this note + its `docs/changes.d/` fragment
  present (the one-row-per-file contract, issue #1123).

## Linked

Implements the #1694 AC4 change-note correction (issue #1826); supersedes the
`2026-11-02-vllm-rocm-cell-timeout-budget` note's **480** value on #1696's
head.
