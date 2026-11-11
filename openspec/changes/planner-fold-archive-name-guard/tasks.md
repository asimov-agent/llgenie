# Tasks

- [x] Guard allow-list extended with the `.archive/` fold prefix, with the byte-parity reason
      (proven: `make check-module-names` -> "[module-name] OK", rc=0)
- [x] Live offender re-pointed to `scripts/llgenie_serve.py` in
      `agents/llgenie-planner/skills/software-development/local-inference-engine-builds/SKILL.md`
      (proven: `pytest tests/test_rename_llgenie_serve.py` -> 16 passed, rc=0)
- [x] `tests/test_rename_llgenie_serve.py` docstring names the third history class (updated test,
      not new test — 16/16 green)
- [x] Notes updated in the same commit: `agent-wiki/2026-11-10-planner-skill-fold-2365.md` +
      `docs/changes.d/2026-11-10-planner-skill-fold-2365.md` (proven: `make check-docs` green in
      lane-preflight)
