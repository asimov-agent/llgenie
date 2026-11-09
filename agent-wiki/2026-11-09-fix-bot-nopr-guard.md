# 2026-11-09 — fix-bot "nothing to fix" no-PR dispatch is a clean skip (issue #2430)

## The defect

`.github/workflows/fix-bot.yml` resolves to no PR branch (a nonexistent/empty branch, or a branch
named main/master) its designed `nothing to fix; the bot never touches main` path, exiting 0. Three
steps still ran from a workspace with **no checkout**: the agent-leg preflight (`uses:
./.github/actions/agent-leg`), the sync (`make bot-sync-branch`), and the transcript upload
(`if: always()`). Since the #798 composite refactor (`ffac22274`, merged `2e9b190cc`, 2026-11-09) the
agent leg is a LOCAL composite action that must be loaded from a checkout, so each of those steps
failed in the empty workspace. Measured on run **42622027619** (head `8608f50e`, `workflow_dispatch`,
conclusion `failure`; job 129176346780):

```
No open PR branch resolved (or it is ) — nothing to fix; the bot never touches main.
##[error]Can't find 'action.yml', 'action.yaml' or 'Dockerfile' under .../.github/actions/agent-leg.
```

A no-PR dispatch is the workflow's own stated no-op, so this was a false red on the main tip.

## What shipped

- **`.github/workflows/fix-bot.yml`** — the two checkout-needing agent-leg steps that lacked the guard
  (the preflight and the `Sync the PR's branch`) now carry `if: steps.pr.outputs.branch != ''`, the
  same guard the checkout, the loop and the push already carry. The transcript upload changed from
  bare `if: always()` to `if: always() && steps.pr.outputs.branch != ''` — it still runs on the real
  repair path (even when the loop fails) but skips the no-PR case. No gate weakened.
- **`tests/test_fix_bot_nopr_guard.py`** — a regression test that reads the `fix` job and fails when
  any checkout-needing leg step loses the guard. Proven both directions: it reds the pre-#2430 tree
  (naming the unguarded preflight) and passes on the fix (3 passed in the container).
- **OpenSpec change `fix-bot-nopr-guard`** + this note + `docs/changes.d` fragment + `CHANGES.md` row.

## Verification

- `docker run llgenie/test:latest python -m pytest tests/test_fix_bot_nopr_guard.py` → 3 passed.
- Negative control: same test on the pre-fix `fix-bot.yml` → 1 failed naming the preflight; restored
  → 3 passed.
- `make check-workflows` → OK; `make lint` → OK; `make openspec-validate NAME=fix-bot-nopr-guard` → valid.
- PR closes #2430.
