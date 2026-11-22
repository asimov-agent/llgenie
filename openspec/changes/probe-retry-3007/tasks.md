# Tasks — probe-retry-3007

## Implementation

- [x] `scripts/gen_trending_quant_catalog.py`: `_probe_status` retries a DEAD-candidate answer (404/410, 5xx, transport error) up to `PROBE_ATTEMPTS` (3) with a short backoff (`PROBE_RETRY_BACKOFF`), classifying on the final answer only; 200/206 and 401/403 return on the first attempt. (proven: pytest tests/test_quant_catalog_compare.py rc=0)

## Tests

- [x] `tests/test_quant_catalog_compare.py` extended on the real-socket loopback harness: 404-then-200 → NOT dead (and the server saw ≥2 requests); 404 across the full budget → dead (exactly `PROBE_ATTEMPTS` requests); 401 → gated with exactly ONE request; hermetic injected-probe paths unchanged. (proven: pytest tests/test_quant_catalog_compare.py rc=0)

## Verification (tick each with its replayable proof)

- [x] `make -s check-wiring` exits 0. (rc=0)
- [x] `make -s check-package-layers` exits 0. (rc=0)
- [x] targeted pytest of `tests/test_quant_catalog_compare.py` and `tests/test_quant_generator_edges.py` and `tests/test_trending_quant_catalog.py` exits 0. (rc=0)
- [x] `make check-quant-catalog` (hermetic) exits 0. (rc=0)
- [x] `make openspec-validate NAME=probe-retry-3007` exits 0. (rc=0)
- [x] `make test-unit` exits 0 at the final branch head. (rc=0 — 4361 passed at head dd9a14e7504fe485a7c0d3d3f1074517a4ce1908)
