# cache-write-package-probe — tasks

- [x] T1 `scripts/engine_image.py`: add `_package_published(ref)` beside `_digest_http` — parse the
      package out of the cache ref, exchange an anonymous GHCR pull token, `GET
      /v2/<package>/tags/list?n=1`; True only when the tags list is non-empty; False for an absent
      package, empty list, unset `REGISTRY`, or an unreachable registry (fail-closed = today's skip).
- [x] T2 `_cache_write_args`: write-eligibility ladder — cache ref present → `--cache-to` unchanged;
      cache ref absent + package published → `--cache-to` + the printed note `absent -> seeding it
      (package published)`; cache ref absent + package absent → no `--cache-to` + the existing
      `cache write skipped; #1880` note. Docstring states the ladder.
- [x] T3 `_buildx`: the package probe is consulted only where a write is decided (the push branch and
      the `CACHE_WRITE` local branch) and only when the cache ref is absent — at most one cache-ref
      probe and one package probe per build; forced and read-only builds consult neither.
- [x] T4 Update the existing #1842/#1880 tolerance tests in `tests/test_engine_force_rebuild.py` so
      they stub the new package probe as ABSENT (their intent — package absent, build cold — stays
      pinned), and pin the present-cache case as NOT calling the package probe.
- [x] T5 New hermetic tests in `tests/test_engine_force_rebuild.py`: `_cache_write_args` seeds on a
      published package; the seeding `--cache-to` reaches the push branch and the `CACHE_WRITE=1`
      local branch; forced/read-only builds issue no package probe; the probe's token+tags/list
      contract (stubbed transport: tags → True, empty/404/exception → False).
- [x] T6 Docs: `agent-wiki/` entry + `docs/changes.d/` fragment + `make changes-index`.
- [x] T7 Verify at the branch head: `pytest tests/test_engine_force_rebuild.py tests/test_engine_cache_namespace.py`
      rc=0; `make check-engine-cache-namespace` rc=0; `make openspec-validate NAME=cache-write-package-probe`
      rc=0; full `make test-unit` rc=0; `make lane-preflight` prints `preflight: OK`.
