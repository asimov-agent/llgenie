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
