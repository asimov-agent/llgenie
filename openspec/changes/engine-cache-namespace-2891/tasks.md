# Tasks — engine-cache-namespace-2891

- [x] `build_base` keys the registry cache ref by the base tag's content digest (`<basehash>-buildcache`)
- [x] `build` keys each cell's registry cache ref by the cell tag's full content suffix (`<pin8>-<content-hash>-<variant>-buildcache`)
- [x] `tests/test_engine_cache_namespace.py` pins both derivations hermetically (unchanged content → same namespace; changed content → new namespace)
- [x] `make check-engine-cache-namespace` wired (target + wiring guard) and green
- [x] Existing seam tests audited: none pin the derived refs (they pass explicit cache refs to `_buildx`; signature unchanged) — full unit suite green (`make test-unit` rc=0, 4040 passed)
- [x] Fast gates green locally (`lint` rc=0, `check-wiring` rc=0 — 455 documents, 397 targets; `lane-preflight` re-run on the final tree)
- [x] `agent-wiki/2026-11-18-engine-cache-namespace-2891.md` written; `docs/changes.d/2026-11-18-engine-cache-namespace-2891.md` fragment added and `CHANGES.md` re-rendered (`make changes-index`); `docs/ENGINES.md` documents the new gate
- [x] `make openspec-validate NAME=engine-cache-namespace-2891` passes (rc=0); out-of-scope `ci_images.py` fixed-ref defect filed as linked issue #2911
- [x] PR opened against upstream `main` referencing issue #2891; issue/PR bodies mirror the ACs with replayable proven strings (AC 1/AC 2 proven by engine-build chain runs — tracked as the landing stamp on issue #2891 once the chain run ids exist)
