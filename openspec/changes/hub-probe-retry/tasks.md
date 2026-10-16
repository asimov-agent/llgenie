# Tasks

- [x] 1. `tests/hub_probe.py`: the one ranged-GET probe — `Probe(exists, detail, attempts)`, `detail` carrying the HTTP status or the transport reason
- [x] 2. The transient set (`429`, `500/502/503/504`, `URLError`, `TimeoutError`, `OSError`) retried on the bounded ladder `1, 2, 4, 8` s (5 attempts); a definitive status returns on the first attempt, un-retried
- [x] 3. `OUTAGE_LIMIT` breaker: after N exhausted transient probes in one process, later probes take one attempt and name the degraded window (bounded time; still a failure, never a skip)
- [x] 4. Both copies deleted: `tests/test_pick_full_registry.py` and `tests/test_trending_quant_catalog.py` call the shared probe and print its `detail` in the assertion message
- [x] 5. `tests/test_hub_probe.py` against a real loopback HTTP server: 206 one request; 404 one request; 204 one request reporting its own attempt count (not the budget it never spent); 503-then-206 two requests; 503-forever 5 requests with the ladder `[1, 2, 4, 8]` recorded; connection refused names the transport error; the breaker caps at one request — **8 passed** in `llgenie/test:latest`
- [x] 6. No per-file copy left: the test that scans the suite asserts neither file defines `_url_exists`
- [x] 7. `tests/test_hub_probe.py` is in the `test-unit` list, so `make test-unit` and `make ci-unit` run it
- [x] 8. Falsified on the real server: the old one-shot probe calls a `503`-then-`206` link missing in 1 request; the shared probe verifies it (`HTTP 206`, 2 attempts), and a sustained `503` reports `HTTP 503 after 5 attempts (15s of backoff)`
- [x] 9. README's pick-matrix section names the shared probe, its retry budget and the breaker; `agent-wiki/2026-10-16-hub-probe-retry.md` records the work with `#256` and `#339`
- [x] 10. `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows` and `make openspec-validate NAME=hub-probe-retry` exit 0
- [x] 11. `make loop` green
