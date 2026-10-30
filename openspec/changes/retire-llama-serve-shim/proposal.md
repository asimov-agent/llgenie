# retire-llama-serve-shim — proposal

Issue: [#816](https://github.com/asimov-agent/llgenie/issues/816)

## Why

`scripts/llama_serve.py` is a compatibility shim whose own docstring says it should already
be gone: *"this shim is removed in a follow-up"*. It was added with the CLI rename (#251,
2026-10-14) "for one release", and the follow-up was never filed — so the promise has no
owner and no date.

Worse, the rename guard keeps the old spelling legal: `ALLOWED_PREFIXES` in
`scripts/module_name_guard.py` lists `scripts/llama_serve.py`, an exemption that exists only
because the file exists. The repo's rule is that the old CLI name is refused in every live
file; that one entry is a hole the guard can never close, and a stray live file could inherit
legal status by sitting beside the shim.

## What Changes

- **Delete `scripts/llama_serve.py`.** Nothing imports or runs it: the installed launcher
  (`~/bin/llgenie`), the Makefile and `docs/ARCHITECTURE.md` all name `scripts/llgenie_serve.py`.
- **Shrink the guard's allowlist** to `scripts/module_name_guard.py` (it must spell the name it
  forbids), `agent-wiki/` and `openspec/changes/` (the dated record of what was true then).
  With the shim gone, `scripts/llama_serve.py` becomes an ordinary offender: a file that comes
  back is refused, not tolerated.
- **Replace the shim-pinning test with the rule it protected.** `tests/test_rename_llgenie_serve.py`
  currently proves `import scripts.llama_serve` hands back `llgenie_serve`. The replacement
  proves the removal rather than assuming it (`importlib.util.find_spec("scripts.llama_serve")
  is None`, the shim path does not exist) **and** proves the surviving entry point actually
  works: `python3 scripts/llgenie_serve.py --help` reaches the CLI.
- **Update the guard's docstring** so it no longer describes a shim that is gone.

## Not covered

- Renaming `scripts/llgenie_serve.py` — the current name is the one the whole tree already uses.
- The `cli-dry-run-grid` OpenSpec change and #797's subprocess-wrapper refactor — separate work.
- Any user who still types the old path: the shim's contract was "one release", and the
  launcher has pointed at `llgenie_serve.py` since #251.

## Impact

- Affected: `scripts/llama_serve.py` (deleted), `scripts/module_name_guard.py`,
  `tests/test_rename_llgenie_serve.py`.
- Gates: `make check-module-names`, `make test-unit`, `make check-docs`.
- Behaviour: the CLI is reachable by exactly one module path; the old name is refused
  everywhere in a live file.
