# Tasks

- [x] 1. `scripts/llgenie_serve.py::_hf_get` catches `(urllib.error.URLError, TimeoutError)` in its transport arm, so a read-phase socket timeout is retried on the existing budget/backoff instead of escaping as a traceback; the docstring says why both classes are named
- [x] 2. The exhausted budget still exits through `[ERROR] HF API still failing after N attempts`, and a stall that clears returns the payload
- [x] 3. `tests/test_llgenie_serve.py::test_hf_get_retries_a_read_phase_timeout`: a REAL local HTTP server accepts and answers nothing (no monkeypatched transport); a stall is retried, the retry's payload is returned, an exhausted budget raises `SystemExit` after exactly the budget's attempts, and `TimeoutError` never escapes
- [x] 4. Falsified: with `scripts/llgenie_serve.py` stashed (the unfixed source) the test fails with `TimeoutError: timed out` — the CI symptom; restored, it passes
- [x] 5. `README.md`'s Hub-transport paragraph names the read-phase `TimeoutError` (not a `URLError`) and that both GET seams retry it, with issue #549
- [x] 6. `agent-wiki/2026-10-23-hf-get-read-timeout.md` records the work with the issue and the PR
- [x] 7. Gates green: `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows`, `make check-pr-hygiene`, `make check-pr-authors`, `make openspec-validate NAME=hf-get-read-timeout`
