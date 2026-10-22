# Tasks — rebase-behind-despite-comment

- [x] 1. OpenSpec change: proposal, spec, this checklist
- [x] 2. `scripts/bot_claims.py`: a comment holds only when it carries a claim marker or an occupying done marker
- [x] 3. `tests/test_rebase_bot_sweep.py`: a behind PR with a plain comment is rebased; a claim marker still holds
- [x] 4. README + agent-wiki record the rule
- [x] 5. Verified: `pytest tests/test_rebase_bot_sweep.py tests/test_bot_claims.py` → 52 passed
