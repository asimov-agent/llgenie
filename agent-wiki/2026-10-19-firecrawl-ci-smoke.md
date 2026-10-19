# The masked web reach runs in CI, on the repository secret

Issue #381 (follow-up of #362/#357). OpenSpec change: `firecrawl-ci-smoke`.

## What was wrong

#362 built `make agent-fetch` and `make search-smoke`, and no job ran either: the repository defined no
`FIRECRAWL_API_KEY` secret, so `tests/fixtures/host-only-wiring.json` recorded `search-smoke` as a
human-run target. A capability only a human with a local key can exercise is not a check.

## What changed

- The owner defined the `FIRECRAWL_API_KEY` repository secret (2026-10-19T21:02Z; names only are ever
  listed — `gh api repos/asimov-agent/llgenie/actions/secrets`).
- New workflow `.github/workflows/search-smoke.yml`: daily 07:11 UTC (+ hand dispatch behind the shared
  owner/collaborator guard), running `make agent-shell-keys-check
  AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` **before** `make search-smoke`, with the key forwarded by
  name (`FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}` → `docker run -e` + the
  `_HERMES_FORCE_` seam).
- The `search-smoke` exception is deleted from `tests/fixtures/host-only-wiring.json`; `make
  check-wiring` fails a record CI now reaches, so the deletion is enforced, not cosmetic.
- New tests in `tests/test_agent_web_reach.py` lock the workflow's shape (its own cron slot, the header
  keys, the key by name, the check ahead of the smoke) and the deleted exception.
- README: the web-reach section states where it runs; the generated dispatch table was refreshed.

## Verification

- `make check-workflows`, `make check-wiring` (66 CI targets now), `make check-dispatch-forms`,
  `make check-docs`, `make check-secret-output`, `make openspec-validate NAME=firecrawl-ci-smoke`.
- `make test-unit`.
- After merge: dispatch `search-smoke.yml` and read the run — that is what proves the secret's VALUE
  works in CI (the local `make search-smoke` already returned HTTP 200 on 959 markdown chars).

## Follow-ups, not folded in

- #380 — no bot leg calls `make agent-fetch` yet, and there is no coverage report (#362 items 4 and 6).
- #382 — `make secret-scan` walks gitignored `tests/__pycache__/*.pyc`.
