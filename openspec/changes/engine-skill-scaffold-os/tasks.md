# Tasks

- [x] 1. `scripts/engine_skill_scaffold.py`: `oses(backs)` derives `os:` from the effective backend list — `metal` alone is `[darwin]`, `metal` plus a Linux backend is `[darwin, linux]`, no `metal` is `[linux]`; `os_note(backs)` renders the same evidence as one sentence
- [x] 2. `skill_text()` writes `os: [<derived>]` instead of the hardcoded `os: [linux]`, and puts `os_note()` as the first item of the scaffold body's to-do list (value + evidence + "check it against the pinned repo")
- [x] 3. The module docstring states the `os:` derivation beside the other registry-stated facts
- [x] 4. `tests/test_engine_skill_scaffold.py` locks both shapes plus the dual shape and the body's provenance line, and asserts the `--backends` override drives `os:` too
- [x] 5. `python3 -m pytest tests/test_engine_skill_scaffold.py` — 11 passed
- [x] 6. The real vendored store derives honestly: `Kapitsa`/`MLX` -> `os: [darwin]`, `llama.cpp`/`Ollama` -> `os: [darwin, linux]`
- [x] 7. `README.md`'s `make engine-skill-scaffold` block, `docs/BOTS.md` and `docs/ARCHITECTURE.md` describe the derived `os:`
- [x] 8. `agent-wiki/2026-10-28-engine-skill-scaffold-os.md` records the work (issue #772) and `CHANGES.md` indexes it
- [x] 9. The unit suite is green — `python3 scripts/unit_tests.py run` (what `make test-unit` runs) `14549 passed, 6 deselected`, and `python3 scripts/lint_linefeeds.py`, `python3 scripts/check_wiring.py check`, `python3 scripts/check_docs.py check` all exit 0 — run through the scripts the make targets call, because this agent container has no Docker daemon for `$(TEST_RUN)`
- [x] 10. The change's tasks are all ticked and parse (`python3 scripts/check_openspec_tasks.py engine-skill-scaffold-os` -> OK); its structural validation is `ci-openspec`'s (`make openspec-validate-all`), which needs the openspec container this agent container does not have
