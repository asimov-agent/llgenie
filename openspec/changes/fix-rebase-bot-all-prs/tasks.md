# tasks — fix-rebase-bot-all-prs

## 1. The workflow

- [x] 1.1 one loop step: `make rebase-bot-sweep` -> `make rebase-bot`, repeated until `none`/`cap`
- [x] 1.2 `max_prs` dispatch input (documented, default 10) bounds the run
- [x] 1.3 a failed rebase calls `make rebase-bot-abort`, is counted, and the loop continues
- [x] 1.4 the step exits non-zero naming the failures

## 2. The Makefile

- [x] 2.1 `rebase-bot-abort` aborts a stopped rebase and returns the tree to `main`
- [x] 2.2 it is declared in `.PHONY` and documented in README

## 3. Tests

- [x] 3.1 the loop, its bound and its stop condition
- [x] 3.2 the abort-on-failure path and the failure exit
- [x] 3.3 the `rebase-bot-abort` target

## 4. Documentation

- [x] 4.1 README's rebase-bot section describes the per-run drain and `max_prs`
- [x] 4.2 `agent-wiki/` entry referencing issue #462 and the PR

## 5. Verification

- [x] 5.1 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 5.2 `make test-unit` green
- [x] 5.3 structural gates (`check-wiring`, `check-docs`, `check-workflows`, `check-dispatch-forms`, `check-pr-hygiene`, `check-pr-authors`, `lint`) green
- [x] 5.4 `make openspec-validate NAME=fix-rebase-bot-all-prs` exits 0 and every task above is ticked
