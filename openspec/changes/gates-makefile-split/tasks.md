# tasks — gates-makefile-split

## 1. The split

- [x] 1.1 `mk/gates.mk` carries ONLY the gates-domain targets (names + recipes byte-identical)
- [x] 1.2 the top `Makefile` keeps version/help/.PHONY/environment and adds `include mk/gates.mk`

## 2. The readers

- [x] 2.1 `scripts/check_wiring.py` resolves includes (`_makefile_list`) for recipes/phony/help
- [x] 2.2 `scripts/check_docs.py` / `scripts/architecture_bot.py` resolve includes (`_makefile_text`)
- [x] 2.3 `scripts/check_dispatch_forms.py` resolves includes (`makefile_targets`)
- [x] 2.4 `scripts/issue_bot_gates.py` resolves includes (`_makefile_text`)
- [x] 2.5 `tests/conftest.py` exposes `makefiles_text` for the suite

## 3. Tests

- [x] 3.1 Makefile-slicing tests read through the resolver (test_wiring, test_check_docs,
       test_check_pr_closing, test_changes_index, test_agent_skills, test_openspec_gate,
       test_macos_install, test_pr_hygiene_changes_index, test_agent_model_pin)
- [x] 3.2 affected unit modules green in the container

## 4. Documentation

- [x] 4.1 `agent-wiki/` entry referencing issue #2457 (#800, superseded #2454)
- [x] 4.2 `docs/changes.d/` fragment + CHANGES.md row rendered via `make changes-index`

## 5. Verification

- [x] 5.1 `make -qp` target list identical and `make help` byte-identical before/after
- [x] 5.2 `make check-wiring` / `make check-docs` byte-identical before/after
- [x] 5.3 `make check-dispatch-forms` / `make check-workflows` / `lint` green on the split tree
- [x] 5.4 merged openspec proposal + spec + tasks ticked (bug-proves gates stay green)
