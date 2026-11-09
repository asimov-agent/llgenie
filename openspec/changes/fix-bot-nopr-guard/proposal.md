# fix-bot-nopr-guard — a "nothing to fix" dispatch is a clean skip (issue #2430)

## Why

`.github/workflows/fix-bot.yml` resolves to no PR branch when the dispatch names a PR that has no
open branch, or an empty/main branch — its designed `nothing to fix; the bot never touches main` path,
which `exit 0`s. Three steps still run from a workspace with NO checkout: the agent-leg preflight
(`uses: ./.github/actions/agent-leg`), the sync (`make bot-sync-branch`), and the transcript upload
(`if: always()`). Since the #798 composite refactor (`ffac22274` → merged `2e9b190cc`, 2026-11-09)
the agent leg is a LOCAL composite action that must be loaded from a checkout, so each step fails in
the empty workspace: run **42622027619** (head `8608f50e`, `workflow_dispatch`, conclusion `failure`;
job 129176346780) shows `##[error]Can't find 'action.yml' .../agent-leg. Did you forget to run
actions/checkout`. A no-PR dispatch — the workflow's own stated no-op — is a false red on the main tip.

## What Changes

- Add `if: steps.pr.outputs.branch != ''` to the two checkout-needing agent-leg steps that lack it,
  matching the guard the checkout and the loop already carry:
  - the preflight `Run the reusable agent-leg preflight (issue #798)` step
  - the sync `Sync the PR's branch with latest upstream main before repairing it (issue #303)` step
- Narrow the transcript upload from `if: always()` to `if: always() && steps.pr.outputs.branch != ''`
  so it still runs on the real repair path (even when the loop fails) but skips the no-PR case.
- Lock it with a regression test (`tests/test_fix_bot_nopr_guard.py`) that reds when any
  checkout-needing leg step loses its guard.

## Capabilities

- **fix-bot-nopr-guard**: a no-PR `workflow_dispatch` of fix-bot is a clean skip.

## Impact

The guarded PR-repair path is byte-identical: when a branch IS resolved, the preflight, the sync, the
loop and the upload each run exactly as before. No gate is weakened, and a no-op dispatch no longer
reds the main tip.
