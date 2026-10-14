# Documentation is part of the change, and it is checkable

## Why

`AGENTS.md` already asked for a README update with every user-facing change and for work records
in `agent-wiki/`, but nothing enforced either, so both drifted: measured on `main`, 19 of the 112
user-facing `##` targets were documented nowhere, a pipeline change could land with no README
sentence, and a work record could be written without ever naming the issue it implements — which
makes it unfalsifiable.

## What changes

- **`AGENTS.md`**: the mandate is mandatory and durable — README *and* the dated `agent-wiki/`
  record, in the same commit, each naming the issue it answers.
- **`make check-docs`** (`scripts/check_docs.py check`): fails when a user-facing `##` target is
  undocumented in `README.md`, when a recorded exception in `tests/fixtures/docs-exceptions.json`
  has gone stale, or when a work record references no issue/PR. `make docs-report` is the human
  view (documented / missing / exception, and every record's references).
- The gate runs as the last step of `make ci-unit`, so it is a real gate, not a suggestion.

## Impact

A change that ships user-facing surface without documenting it now fails CI. A target that
legitimately stays out of the README is recorded with a reason and a date, and the record fails
once the README documents it, so the exception file cannot rot.
