# A new test file bootstrapping `scripts/` reds the import-roots ratchet (keep the baseline honest, never skip it)

When a PR adds a test that reaches `scripts/` via `sys.path.insert(...)` + a bare `import`, CI's
`linux/unit` (via `make ci-unit`) can fail on the **import-roots ratchet** (`make check-import-roots`,
issues #796/#1101) even though the tests pass locally:

```
[import-roots] bare: a NEW import root is refused — (55 now, 54 recorded)
  tests/test_<new>_line.py:23
[import-roots] sys-path: a NEW import root is refused — (35 now, 34 recorded)
  tests/test_<new>_line.py:21
make: *** [Makefile:403: check-import-roots] Error 1
```

Symptoms: `linux/unit` red ~11–14 min in; `ci-verdict` red as its downstream. The failing row is
`linux / unit` itself. The fix is NOT to weaken the gate and NOT to restructure your test to avoid
bootstrapping `scripts/`.

The baseline at `tests/fixtures/import-roots-baseline.json` is a **measurement, not a constant** (the
script's own docstring): every test that bootstraps its own path adds a site, and the baseline records
what the branch produces. Existing entries (agents-line test at `test_pr_hygiene_agents_line.py:19`/`:17`,
the import-roots test at `test_import_roots.py`) are legitimate — a NEW test adding a bootstrap root is
the same class, so re-record:

```
python3 scripts/check_import_roots.py ratchet --update
```

The diff must add EXACTLY the one or two new `tests/test_<new>_line.py:<n>` sites (count +1) and must
NEVER remove an existing recorded site (that would silently lower the floor). `make check-import-roots`
goes green after. Re-record is the sanctioned path (#1101); a `--allow` prefix is the recorded-exception
path. Never hand-edit a baseline to force green.

Parallel lesson: a new `make` target that runs a per-PR body gate must be added to `.PHONY` AND
documented in `docs/BOTS.md` — a missing doc row reds `make check-docs` with `MISSING make <target>`.
