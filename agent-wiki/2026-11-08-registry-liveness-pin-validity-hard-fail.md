# 2026-11-08 — registry-liveness turns the committed-tag pin-validity gate into a hard-failing job (issue #2190, PR #2245)

The #2190 class — a committed engine tag (pin + params hash) whose image was never
published — must turn the scheduled `registry-liveness` run RED, not a silently-green
issue-filer. Previously the workflow ran `make check-engine-launchers CHECK_REGISTRY=1
ARCH=all`, captured `rc`, printed it, and `exit 0` regardless — so a committed
`manifest unknown` (tensorfold/cuda at `ef27f74f`, #1519) 404'd while the job reported
success and its fuzzy issue-dedup matched an unrelated open issue (#391): the top-page
issue-filer concluded success and no tracking issue was filed.

## What changed (PR #2245, refinements on top of the committed-set gate #2248)

- The liveness job now runs the full-fleet gate as its OWN hard-failing step:
  `make check-engine-pins-published ALL=1`, then `exit "$rc"`. `ALL=1` sweeps every
  committed enabled cell's exact tag (not just cells a PR repins), so a pin a prior
  merged bump committed but never pushed reds this scheduled run and stays red until
  `engine-build` `push=true` publishes it.
- The issue-filer still runs on `if: always()` — a gate red never suppresses the
  tracking issue — but it dedups on the exact image tag (`search "\"$tag\""`) instead
  of a fuzzy engine-name search that matched the wrong issue.
- The filer skips filing when BOTH the fleet gate and the launcher check are green
  (`rc == 0` on both), so a resolved commitment stops producing issues.
- `scripts/check_engine_pins_published.py` already carries the full-fleet sweep
  (`committed_cells()` / `check_committed()`, issue #2248); this PR wires it into the
  liveness monitor as the job's exit and adds a make target that invokes `check --all`.

## Key decision

Publish, not repin: the committed v1.2.1 pin (`ef27f74f`) is the intended latest
(#1519); repinning to the older published `dee65c75` would be a downgrade. The gap was
a cell committed but never pushed, so the fix is CI-owned publish (`engine-build`
`push=true`), plus the hard-failing guard that makes the recurrence loud and the
issue-filer that tracks it.

## Status

Behavioral surfaces: `.github/workflows/registry-liveness.yml`, `Makefile`.
Verified: dispatched `engine=tensorfold arch=cuda` publish run confirmed `PUBLISHED` in
GHCR at the pinned commit; the full-fleet gate reds on a committed 404 and goes green
once that tag resolves.
