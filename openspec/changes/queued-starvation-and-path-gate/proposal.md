# A starved queue is documented as supply, and a PR stops queueing rows it did not need

## Why

Two measured facts from 2026-10-28, one issue (#817):

1. **The queue starved and nobody could see it.** 18 runs `queued` with 0 `in_progress`, GitHub
   reporting `Actions: operational`. Every open PR's checks sat `pending`, every PR read `BLOCKED`, and
   `auto-merge` / `fix-bot` / `rebase-bot` correctly did nothing. `docs/BOTS.md` described the
   `queued-alarm` workflow as "reports CI jobs queued far too long" and nothing else, so three agents
   spent about an hour on it and one recommended merging to drain the queue — which cannot work, because
   `ci.yml` sets `cancel-in-progress` on `pull_request` and a push re-queues the whole matrix.
2. **Every PR queued work it had not changed.** Measured from the run's own jobs: a security-script PR
   (#786, run 40698685046) queued **28 jobs** — all four `engine-base-*` rows, `scanner-images`,
   `engine-matrix` and the published rows — for a diff that touched none of them. An engine-bump PR
   (#803, run 40704612341) queued 26, four of which rebuilt toolchains it had not touched.

The engine matrix already narrowed itself by changed tag (`make list-engine-images CHANGED=<ref>`,
issue #153). The shared base toolchains had no such gate.

## What changes

1. `docs/BOTS.md` gains **A queue is not a verdict**: the two commands that measure supply
   (`gh run list --json status` counts, `gh run view <id> --json jobs` per-job wait), the distinction
   from #801 (one PR's empty rollup with `mergeStateStatus: DIRTY` is a branch needing a rebase), and
   "never merge or push to drain the queue" with the measured cost. Two proposed discriminators are
   recorded as wrong because they were measured first: `runner_name` is `null` for an `in_progress` job
   too, and `startedAt` is set at enqueue rather than at pickup.
2. `scripts/engine_image.py` gains `base_matrix(changed)` — one row per shared toolchain whose rendered
   `Dockerfile.<backend>` differs from a ref, or the single `none` placeholder row (an empty include
   list is illegal). `make list-engine-base-images` is its entry point, beside `list-engine-images`.
3. `.github/workflows/ci.yml`'s `engine-matrix` job emits that matrix beside the engine one, from the
   same changed ref, and `engine-base` takes its matrix from it. Every step carries the same
   allowlisted `none`-row skip the `engine-image` rows use — no job-level `if:` and no skipped step, so
   `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` keeps its guarantee (its allowlist gains
   the one literal, `matrix.backend != 'none'`).

## Impact

- A PR that touches no base toolchain queues **1** `engine-base-none` row instead of 4; one that
  touches none publishes no rows it cannot use. A push whose `before` is unknown keeps the full sweep.
- Nothing is dropped silently: the placeholder row is visible in the run's job list, and the engine
  matrix's existing gate is untouched.
- Rows deliberately left wide: `ci-images` (one cheap pull-or-build that every job pulls from),
  `scanner-images` (one job; removing its slot needs a job-level `if:` or a workflow split that would
  change the required-check set — an owner decision, not this change), and the `pipeline.yml` Linux/macOS
  suites (they are the actual test gate).
