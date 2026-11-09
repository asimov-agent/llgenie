# reuse-agent-leg — Tasks

Checklist of record. The ordered agent-leg preflight (JEV #238, shell-keys #358,
routing-smoke #407) plus the REDACTED-transcript upload (#359) move into one
composite action; a reusable `agent-leg.yml` workflow exposes a plain leg as
`workflow_call`; the six agent legs call the preflight; the gate reddens an
inline one. `scripts/scrub_log.py` is untouched.

## Composite action + reusable workflow

- [x] 1.1 Add `.github/actions/agent-leg/action.yml`: JEV, shell-keys,
      routing-smoke (opt-in) and the REDACTED-transcript upload steps
- [x] 1.2 Add `.github/workflows/agent-leg.yml` (`on.workflow_call`) with the
      leg inputs (`target`, `skill`, `push`, `timeout`, `transcript`, checkout
      shape) running one agent leg job with its own timeout
- [x] 1.3 The JEV / shell-keys / routing-smoke steps exist in exactly ONE place
      in the tree (the composite action)

## Migrate the six agent legs

- [x] 2.1 `issue-refiner.yml` (no-push shape) calls the preflight and is green
- [x] 2.2 `architecture-bot.yml` (push shape) calls the preflight and is green
- [x] 2.3 `issue-bot.yml` calls the preflight
- [x] 2.4 `rebase-bot.yml` calls the preflight
- [x] 2.5 `fix-bot.yml` calls the preflight
- [x] 2.6 `registry-sync-review.yml` calls the preflight
- [x] 2.7 no `.github/workflows/*.yml` inlines `make agent-jev-preflight` or
      `make agent-shell-keys-check`

## Gate

- [x] 3.1 `scripts/check_workflows.py` reds on a workflow inlining both preflight
      `make` calls (proven by a test in `tests/test_workflows_valid.py`)
- [x] 3.2 `make check-workflows` passes with all six legs migrated
- [x] 3.3 `scripts/scrub_log.py` diff from `main` is empty

## Docs + verification (final)

- [x] 4.1 OpenSpec `proposal.md` / `spec.md` / `tasks.md` written and
      `make openspec-validate NAME=reuse-agent-leg` passes
- [x] 4.2 `agent-wiki/2026-11-09-reuse-agent-leg.md` note (references #798 and
      the PR) and a `CHANGES.md` index row, committed with the change
- [x] 4.3 `make lane-preflight` passes (lint, check-workflows, check-wiring,
      check-docs, check-pr-hygiene, openspec-tasks-check)
