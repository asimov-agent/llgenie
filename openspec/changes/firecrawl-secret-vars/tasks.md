# Tasks

- [x] 1. `scripts/check_secret_output.py`: `FIRECRAWL_API_KEY` joins `SECRET_VARS` (the one list the static guard and `scrub_log` read)
- [x] 2. `tests/test_secret_output.py`: the roster test derives from `AGENT_SHELL_KEYS` in the Makefile as well as workflow `secrets.<NAME>`, and a printed `$FIRECRAWL_API_KEY` is a finding
- [x] 3. `tests/test_scrub_log.py`: the redactor masks a Firecrawl value raw / URL-encoded / base64, with a non-zero count
- [x] 4. `agent-wiki/2026-10-19-firecrawl-secret-vars.md`: the work record, referencing #379 and PR #383; `README.md` notes the one list now carries it
- [x] 5. Verification: `make test-unit` (4805 passed, 3 deselected), `make check-secret-output` OK, `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate NAME=firecrawl-secret-vars`
