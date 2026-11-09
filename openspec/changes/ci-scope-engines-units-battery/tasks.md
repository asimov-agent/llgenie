# Tasks

- [x] 1. `scripts/ci_scope.py`: add `"engines"` to the `_STAGES["unit"]` tuple so a `skills/engines/**`
      (or `containers/engines/**`) change re-includes `linux/unit`. Read-only classifier widening.
- [x] 2. `tests/test_ci_scope.py`: assert the `engines`-class skill path re-includes `unit`, with the
      negative controls (a non-engine `agents/**` skill still selects `unit` via `skills`; a `docs`-only
      path still skips) and a Makefile regression guard that the five security gates live under `ci-unit:`.
- [x] 3. `tests/test_ci_scope_trigger.py`: assert the `skills/engines/*/SKILL.md` trigger-half — it is NOT
      a pure doc and the `engines` class now selects `linux/unit`.
- [x] 4. `openspec/changes/ci-scope-engines-units-battery/` proposal + spec + tasks (this change) and its
      `agent-wiki/` note + `docs/changes.d/` fragment.
- [x] 5. `python3 scripts/ci_scope.py --paths skills/engines/vllm/SKILL.md` prints `job=linux/unit run`;
      `tests/test_ci_scope.py` + `tests/test_ci_scope_trigger.py` pass (49 in `llgenie/test:latest`);
      `make lint`, `make check-docs`, `make check-workflows` green; `make openspec-validate
      NAME=ci-scope-engines-units-battery` green.
