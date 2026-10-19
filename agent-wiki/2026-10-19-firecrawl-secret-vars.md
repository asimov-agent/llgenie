# The Firecrawl key joins the ONE credential list

Issue #379 (follows the parent #357 and #362/#369). PR #383. OpenSpec change: `firecrawl-secret-vars`.

## What was wrong

`FIRECRAWL_API_KEY` became a credential the repo forwards to the agent (#362), but it never joined
`scripts/check_secret_output.py::SECRET_VARS` — the one list `make check-secret-output` and
`scripts/scrub_log.py` both read. Measured on `main@829c6ec`: `scrub_log.redact` masked a Firecrawl
value only when its shape matched `Bearer …`; raw, in a URL, or in a body it survived with a
redaction count of 0. The roster test that should have caught it derived names from
`secrets.<NAME>` in workflows only, and the repo secret does not exist yet (so no workflow names it).

## What changed

- `SECRET_VARS` gains `FIRECRAWL_API_KEY`.
- `tests/test_secret_output.py::test_the_secret_list_matches_the_repo_secrets` now also compares
  against the Makefile's `AGENT_SHELL_KEYS`, so a key added to the forwarding seam but missing from
  the guard list reds `make test-unit`.
- New regression tests: a printed `$FIRECRAWL_API_KEY` is a `prints-secret-value` finding, and the
  redactor masks the value raw / URL-encoded / base64.
- README + AGENTS.md state the one-list rule (forwarded ⇒ scanned and redacted).

## Verification

- `docker run … llgenie/test:latest python -m pytest tests/test_secret_output.py tests/test_scrub_log.py`
  → 39 passed.
- `make check-secret-output` → OK, 302 files, list now names `FIRECRAWL_API_KEY`.
- `make test-unit`, `make check-docs`, `make lint`, `make openspec-validate NAME=firecrawl-secret-vars`.

## Follow-ups filed, not folded in

- #380 — no bot leg calls `make agent-fetch`, and no coverage report (#362 items 4 and 6).
- #381 — the `FIRECRAWL_API_KEY` repository secret does not exist; wire `search-smoke` into a job.
