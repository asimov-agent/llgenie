# Retire the orphan reusable agent-leg workflow

## Why

`make code-review-scan` filed #2443: `.github/workflows/agent-leg.yml` declares
`workflow_call` as its only trigger and NO workflow in `.github/workflows/` references
`workflows/agent-leg.yml` — the reusable half of issue #798's `reuse-agent-leg` change
(1.2) shipped, but the migration that consumed it (tasks 2.1–2.6) landed entirely as
COMPOSITE-ACTION calls (`uses: ./.github/actions/agent-leg`), so the reusable workflow
was born orphaned. All six agent legs run the same preflight through the composite
action today (measured at `origin/main@ac0cd6736`: architecture-bot, fix-bot, issue-bot,
issue-refiner, rebase-bot, registry-sync-review each call `./.github/actions/agent-leg`).

## What Changes

- DELETE `.github/workflows/agent-leg.yml`. The composite action already IS the single
  code path for the ordered agent-leg preflight (#798's requirement 1: the JEV /
  shell-keys / routing-smoke steps exist in exactly ONE place); the reusable wrapper is
  a second mechanism for the same job with zero callers — dead weight that is still
  validated and pinned as if live machinery (violates the one-code-path rule).
- DELETE the `tests/fixtures/workflow-run-exemptions.json` entry
  `agent-leg — the reusable agent leg`: `make check-workflows` reports a STALE exemption
  once it names no workflow (measured on this branch: removing the workflow without the
  entry reds check-workflows with exactly that message), so the exemption retires with
  the workflow it exempted.
- REMOVED the `reuse-agent-leg` spec requirement "a reusable agent-leg workflow exists";
  the composite-action requirement, the inline-preflight redness requirement, and the
  scrub_log requirement are untouched.
- No caller is rewired (none exists); no preflight moves (the composite action is
  untouched); a future whole-job reusable leg is recoverable from git history if ever
  needed.

## Impact

`affa46a30d65f...` — the `reusable-orphan/agent-leg.yml` finding key disappears from
`make code-review-scan` (the workflow file is gone, so the check cannot report it).
