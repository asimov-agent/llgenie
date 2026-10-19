# Tasks

- [x] 1. `scripts/scrub_log.py`: values read BY NAME from the environment (the ONE list in `check_secret_output.py::SECRET_VARS`), every raw / URL-encoded / base64 spelling masked, credential shapes masked, a bounded tail printed with a COUNT, exit 2 on a missing input — never a value, a prefix or a slice
- [x] 2. Makefile: `HERMES_LOG` / `HERMES_LOG_SCRUBBED` / `HERMES_LOG_TAIL`, ONE `$(call scrubbed_run,…)` macro (subshell so a leg's `exit` cannot skip the redaction; the command's exit status preserved), and the public `scrub-log` target
- [x] 3. Makefile: every public agent leg goes through the macro — `issue-refiner`, `issue-bot-triage`, `implement-issue`, `hermes-smoke`, `rebase-bot-agent`, `agent-jev-preflight`, `fix-loop-image` (`LOG=` now receives the REDACTED copy); `.PHONY` + `##` help lines
- [x] 4. `.gitignore`: `hermes-run.log` and `hermes-run.scrubbed.log`
- [x] 5. `.github/workflows/{fix-bot,issue-bot,issue-refiner,rebase-bot}.yml`: upload the REDACTED transcript as the `agent-transcript-redacted` artifact, never the raw log
- [x] 6. `tests/test_scrub_log.py` in `make test-unit`: spellings + shapes, the short-value guard, the loud missing input, the bounded tail, the REAL macro through the real Makefile (redaction + exit status), every public leg uses the seam, every bot job publishes the redacted file
- [x] 7. `AGENTS.md`: the durable rule — no leg prints its stream raw; the REDACTED copy is the artifact
- [x] 8. `README.md`: the section (the seam, the artifact, `make scrub-log`, `HERMES_LOG_TAIL`)
- [x] 9. `agent-wiki/2026-10-19-agent-log-redaction.md`: the work record (issue #359 + the PR it opens)
- [x] 10. Verification: `pytest tests/test_scrub_log.py` (9 passed), `make check-wiring`, `make check-docs`, `make check-secret-output`, `make check-workflows`, `make lint`, `make openspec-validate NAME=agent-log-redaction`
