# tasks — fix-rebase-bot-unknown-state

## 1. The sweep

- [x] 1.1 `resolve_state` + `UNKNOWN_ATTEMPTS`/`UNKNOWN_DELAY_S` in `scripts/rebase_bot_sweep.py`
- [x] 1.2 Defer (never silently pass over) a PR that stays `UNKNOWN`, and expose it on the result
- [x] 1.3 CLI flags `--unknown-attempts` / `--unknown-delay`

## 2. The workflow

- [x] 2.1 `Rebase it …` exports `GH_TOKEN` so the outcome comment + `done` marker post

## 3. Tests

- [x] 3.1 UNKNOWN→DIRTY is picked
- [x] 3.2 a permanently UNKNOWN PR is deferred by name
- [x] 3.3 the rebase step carries `GH_TOKEN`

## 4. Documentation

- [x] 4.1 README's rebase-bot section states the computed-state rule and the marker token
- [x] 4.2 `agent-wiki/` entry referencing issue #453 and the PR

## 5. Verification

- [x] 5.1 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 5.2 `make test-unit` green
- [x] 5.3 the structural gates (`check-wiring`, `check-docs`, `check-workflows`, `check-pr-hygiene`, `check-pr-authors`) green
- [x] 5.4 `make openspec-validate NAME=fix-rebase-bot-unknown-state` exits 0 and every task above is ticked
