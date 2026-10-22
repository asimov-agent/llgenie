# Tasks — guard-repo-bot-same-repo-head

- [x] 1. OpenSpec change
- [x] 2. `.github/workflows/*.yml`: all 13 guard sites gain `HEAD_REPO` and the same-repo bot allowance,
      byte-identically
- [x] 3. `tests/test_workflow_guards.py`: execute the real guard script under bash against a real fake
      `gh` for owner / write collaborator / stranger / bot on same-repo, foreign and missing heads, plus
      the `HEAD_REPO` declaration and byte-identical checks
- [x] 4. README + agent-wiki
- [x] 5. Verified: `pytest tests/test_workflow_guards.py` → 14 passed; the guard from `origin/main`
      refuses the same-repo bot case (exit 1) while the new one admits it (exit 0)
