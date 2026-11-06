# engine-build matrix timeout is matrix-aware (rocm ~360 / other 240)

## Background (measured 2026-11-06)

`engine-build.yml`'s build job carried a **flat `timeout-minutes: 240`**
on every matrix cell (line 163). The heavy vllm/rocm cell repeatedly
cancelled on that wall while still compiling — killed at the cap, reading
`cancelled`, never a verdict. Measured over the last 80 runs, job name
`engine-build-vllm-rocm`:

| outcome | runs | min | p50 | max |
|---|---|---|---|---|
| completed SUCCESS | 4 | 8m | 59m | 107m |
| CANCELLED (killed on wall) | 13 | 9m | 218m | 241m |

Five cancelled runs ended at exactly **241m** — the hard 240m cap; the
completed-success band is p50 59m / max 107m. Cheap cells are unaffected:
`sglang-cuda` completes p50 11m / max 13m.

## The answer

The timeout is now **matrix-aware by variant**:

```yaml
timeout-minutes: ${{ (matrix.variant == 'rocm') && 360 || 240 }}
```

- **rocm** cells (the heavy GPU/rocm class) get **~360m** — 3.4× the max
  completed-success, sized from the measured band (#1694's "2× the ~107m
  band plus headroom"), so a genuine slow build can finish instead of being
  silently cancelled.
- **cuda / cpu / vulkan** cells keep the **240m** budget — a hung cheap cell
  still fails fast (cuda/vulkan already complete well under the band).

Capacity only: no `ci-verdict`/`ci-scope` gate touched, no `make
build-engine` step changed. This lands the owner-authored intent from
#1609 (`d4b6dd40`, closed-unmerged) at the current ruling (#1818/#1694:
~360, not the prior 480) and gives #1694's criterion 1 its tracked work
item, so #1696 has a linkable target for its `## Not covered`.

## Acceptance hedged honestly

Criterion 2 (a verified `push=true` vllm/rocm cell that COMPLETED-SUCCESS
at the raised cap) cannot be produced while the cap is still 240 on main —
a `push=true` dispatch is owner-guarded (#1088) and the new cap only
exists after merge. So the band + this change are the honest evidence on
the introducing PR; the completed-run proof is the post-merge release
condition and is recorded as deferred, not fabricated.
