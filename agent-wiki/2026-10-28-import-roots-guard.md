# One import root for the tests, enforced by a ratchet (#796)

At `798cbee` the suite has **104** files carrying their own `sys.path.insert` and **141** top-level bare
imports of `scripts/` modules — measured, not quoted:

```
$ python3 scripts/check_import_roots.py report
[import-roots] counts: {'sys-path': 104, 'bare': 141, 'syntax': 0}
```

The reason a count is not a verification: a file that inserts a path entry and then imports nothing from
it looks migrated. So the guard is a **ratchet**, not a gate. `tests/fixtures/import-roots-baseline.json`
records the counts; `make check-import-roots` fails when a count rises and passes when one falls. That is
what lets the guard land *before* the migration: landing a plain gate would red the suite on the commit
that added it, and landing no gate means the next file adds a 105th root unnoticed.

Two rules, both about shapes no ordering of edits can make work: a `sys.path.insert`/`append` outside
`tests/conftest.py`, and a bare `import hf_auth` where `scripts/hf_auth.py` exists (the package path is
`from scripts.hf_auth import …`). An unparseable file is its own finding rather than a silent skip —
the previous attempt at this migration broke on exactly that kind of invisibility, with an import regex
anchored at end-of-line so a trailing `# noqa` blocked the rewrite.

## Regression fix (2026-10-30, PR #953)

The import-root migration shared `scripts.hf_auth` between `test_hf_auth.py` and
`test_hf_download_retry.py`, which its per-file top-level imports (a separate module family via
`sys.path.insert`) never did. `test_hf_auth`'s stderr-announce test drives `hub_open` with an
always-429 opener to exhaustion, leaving `scripts.hf_auth._rate_limited` at `RATE_LIMIT_WAITS+1`;
the shared counter made `test_chunk_download_waits_out_a_429` and
`test_preflight_probe_waits_out_a_429` raise on their first 429 (2 failed) under alphabetical order,
while `main@f289e786` passed all 18.

Fix: a function-scoped autouse fixture in `test_hf_download_retry.py`
(`_fresh_rate_limit_budget`) resets `scripts.hf_auth._rate_limited` to 0 per test via `monkeypatch`,
recovering the isolation under the one import root. Both the alphabetical run and the reverse order
pass (18 passed). Issue: [#953](https://github.com/asimov-agent/llgenie/issues/953).
