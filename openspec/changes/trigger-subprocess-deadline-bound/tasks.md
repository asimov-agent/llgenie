# Tasks

- [x] `_sh` and the dispatch `subprocess.run` cap each call at `SUBPROCESS_TIMEOUT` (30s) and yield `""`/continue on `TimeoutExpired` instead of blocking, so the poll loop's own deadline stays authoritative.
- [x] A regression test drives a real slow subprocess (sleep-10 child) with the cap shrunk (1s) and asserts a prompt `""` return in well under the child's sleep.
- [x] Existing `tests/test_engine_build_trigger.py` battery stays green (7 passed) alongside the new test; `check-docs`, `changes-index`, `lint_linefeeds` green.
- [x] Docs per convention: this openspec change dir accompanies the code; `docs/changes.d/2026-11-06-trigger-subprocess-deadline-bound.md` + `agent-wiki/` note + `CHANGES.md` already in the PR.
- [x] PR carries `closes #1838`; normal review flow (#1644 acceptance write-back, owner merges).
