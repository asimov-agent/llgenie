# tasks — fix-rebase-bot-done-marker

## 1. The sweep

- [x] 1.1 `rebased_today` parses `bot_claims.DONE_RE` and counts only `rebase-bot … rebased` dated today

## 2. The actor

- [x] 2.1 `comment()` takes the kind; success records `rebased`, every failure records `gave-up`

## 3. Tests

- [x] 3.1 a claim-only thread is NOT "already rebased today"
- [x] 3.2 a `rebased` done marker is the record
- [x] 3.3 a `gave-up` marker does not record the day
- [x] 3.4 the actor's failure paths write `gave-up`, its success path writes `rebased`

## 4. Documentation

- [x] 4.1 README's rebase-bot section names the marker it reads
- [x] 4.2 `agent-wiki/` entry referencing issue #457 and the PR

## 5. Verification

- [x] 5.1 `pytest tests/test_rebase_bot_sweep.py` green
- [x] 5.2 `make test-unit` green
- [x] 5.3 structural gates (`check-wiring`, `check-docs`, `check-workflows`, `check-pr-hygiene`, `check-pr-authors`, `lint`) green
- [x] 5.4 `make openspec-validate NAME=fix-rebase-bot-done-marker` exits 0 and every task above is ticked
