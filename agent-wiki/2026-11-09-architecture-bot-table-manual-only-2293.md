# ARCHITECTURE bot table records fix-bot + run-failure-reactor as manual-only (issue #2293, #2307)

**Implements:** issues #2293 + #2307 (owner directive 2026-11-08). PR #2307/4d7763a3 made both
red-PR workflows manual-only (`workflow_dispatch` only) and re-stated `docs/BOTS.md`, but left
`docs/ARCHITECTURE.md`'s bot table stale: `fix-bot.yml | 17 * * * *` (with a `workflow_run` on failed
CI) and `run-failure-reactor.yml | — (workflow_run)` still described auto-triggers the tree no longer
has at this sha (or at origin/main 5cc544cf).

## What changed

Both rows in `docs/ARCHITECTURE.md` now read `— (workflow_dispatch only)`, name directive #2293, and
drop the dead `schedule` / `workflow_run` mechanics. A reader of the architecture document now learns
the shipped shape — a red PR is surfaced to a person, not auto-filed or auto-repaired — and a re-added
non-dispatch trigger in either workflow fails `make check-workflows` (negative control from #2293).

Measured at 5cc544cf: `awk '/^on:/,/^jobs:/'` on both `fix-bot.yml` and `run-failure-reactor.yml`
shows `workflow_dispatch` only. Gates green on the branch: `make check-architecture-census`,
`make check-docs`, `make check-wiring`, `make lint`.

Not covered: `docs/BOTS.md:2613`'s surviving "hourly schedule + workflow_dispatch" fix-bot sentence is
a separate docs-lane defect (#2240 audit, tracked separately); it is finally corrected on PR #2323 at
head 9f89cd68.
