# fix-bot-nopr-guard — Tasks

Checklist of record. The three fix-bot steps that need a checkout (agent-leg preflight, sync,
transcript upload) are gated on a resolved PR so a "nothing to fix" no-PR dispatch is a clean
success (issue #2430); a regression test locks it.

## Workflow change

- [x] 1.1 The agent-leg preflight step carries `if: steps.pr.outputs.branch != ''`
- [x] 1.2 The sync step carries `if: steps.pr.outputs.branch != ''`
- [x] 1.3 The transcript upload is `if: always() && steps.pr.outputs.branch != ''` (not bare
      `always()`)

## Regression test

- [x] 2.1 `tests/test_fix_bot_nopr_guard.py` asserts the three checkout-needing steps carry the guard
- [x] 2.2 Negative control: the guard check reds when a step loses it (pre-#2430 shape caught)
- [x] 2.3 The test runs in the discovered unit suite (`scripts/unit_tests.py select` picks it up)

## Docs + verification (final)

- [x] 3.1 OpenSpec `proposal.md` / `spec.md` / `tasks.md` written and
      `make openspec-validate NAME=fix-bot-nopr-guard` passes
- [x] 3.2 `agent-wiki/2026-11-09-fix-bot-nopr-guard.md` note (references #2430 and the PR) and a
      `docs/changes.d/2026-11-09-fix-bot-nopr-guard.md` index fragment, committed with the change
- [x] 3.3 `make lane-preflight` passes (lint, check-workflows, check-wiring, check-docs,
      check-pr-hygiene, openspec-tasks-check)
