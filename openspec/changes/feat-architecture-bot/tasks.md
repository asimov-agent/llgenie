# tasks — feat-architecture-bot

## 1. Deterministic half

- [x] 1.1 `scripts/architecture_bot.py`: `surface`, `drift`, `brief` (real tree, real git, no model)
- [x] 1.2 `scripts/architecture_bot.py`: `publish` — one issue, one branch `agent/architecture-<stamp>`, one PR ending `closes #<n>`; no-op on no drift/an open architecture PR; refuses an empty doc
- [x] 1.3 `make architecture-bot-brief` / `architecture-bot-publish` wired to it

## 2. The agent leg

- [x] 2.1 `_architecture-bot-doc` prompt restricted to `docs/ARCHITECTURE.md`
- [x] 2.2 `make architecture-bot-doc` — `require_env`, agent image, `AGENT_SHELL_FORWARD`, `scrubbed_run`
- [x] 2.3 `make architecture-bot` chains brief -> doc -> publish for a manual local run

## 3. Workflow

- [x] 3.1 `.github/workflows/architecture-bot.yml`: cron `47 */6 * * *`, dispatch (`dry`, `doc`), guard first, own concurrency group
- [x] 3.2 Steps: checkout main (PAT) -> `bot-sync-main` -> JEV preflight -> shell-keys check -> hermes-smoke -> brief -> doc -> publish -> redacted transcript upload -> summary

## 4. Documentation

- [x] 4.1 `docs/ARCHITECTURE.md` seeded from the real tree
- [x] 4.2 README: the bot's section, targets, and the regenerated dispatch table
- [x] 4.3 `agent-wiki/` entry referencing issue #449 and the PR

## 5. Verification

- [x] 5.1 `tests/test_architecture_bot.py` covers every scenario in `specs/architecture-bot/spec.md`
- [x] 5.2 `make test-unit` green with the new test file discovered
- [x] 5.3 `make check-wiring`, `make check-docs`, `make check-dispatch-forms`, `make check-workflows` green
- [x] 5.4 `make openspec-validate NAME=feat-architecture-bot` exits 0 and every task above is ticked
