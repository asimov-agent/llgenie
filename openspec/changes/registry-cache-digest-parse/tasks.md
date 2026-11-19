# Tasks

- [x] 1. `scripts/registry_cache_orphans.py`: replace `digest_of`'s exact-prefix line scan with
      `_extract_digest(ref, text)` consulting module-level `_DIGEST_RE = re.compile(r"digest:\s*(sha256:[0-9a-fA-F]{16,})",
      re.IGNORECASE)`; SystemExit wording unchanged; `digest_of` still parses `out.stdout + out.stderr`
      through the `run_ok` seam
- [x] 2. `tests/test_registry_cache_orphans.py`: keep the injected-resolver gc tests; add three cases
      that drive the REAL `digest_of` via a monkeypatched `run_ok` — the captured padded imagetools
      header, the legacy single-space form, and a no-digest refusal (`pytest tests/test_registry_cache_orphans.py`
      rc=0, 11 passed)
- [x] 3. `make check-wiring` sees the change wired (script unchanged at the target, test module present)
- [x] 4. OpenSpec change `registry-cache-digest-parse` present with proposal.md, spec.md and this
      tasks.md ticking the acceptance as verified
- [x] 5. Docs: `agent-wiki/2026-11-19-registry-cache-digest-parse.md` entry naming #2924, indexed in
      CHANGES.md; `make check-docs` green
- [x] 6. `make test-unit` green (hermetic) with the full suite; `make lint` green
