# Why
`scripts/gen_trending_quant_catalog.py::_probe_status` classifies a quant plan from a SINGLE ranged GET: 200/206 is `ok`, 401/403 is `gated`, and everything else (404/410, a 5xx, a transport error) is `dead` — "nothing serves it, drop it". On 2026-11-22 the Hub 404'd live `unsloth/Qwen3.8-27B-GGUF` links transiently: `ci-hf-live` run `45010151478` failed on `Qwen3.8-27B-UD-IQ2_S.gguf`, and a local `check-quant-catalog LIVE=1` replay minutes later failed on `Qwen3.8-27B-UD-Q6_K_L.gguf`, while `curl -I` answered HTTP 302 on the same URLs seconds before and after each failure. One flaky probe reddened the post-merge live battery and — per the post-merge rules — blocked landing until a data refresh chased it.

# What Changes
- MODIFIED `quant-catalog-live-probe`: classifying a plan DEAD now requires a BOUNDED retry budget. `_probe_status` retries a DEAD-candidate answer (404/410, any 5xx, a transport error) up to `PROBE_ATTEMPTS` (3) total attempts with a short backoff, and classifies on the FINAL answer only: a link that flips to 200/206 on a later attempt is `ok`. `PROBE_OK` (200/206) and `PROBE_GATED` (401/403) return on the first attempt — gated is a stable access decision, not a blip, and a healthy link pays no retry cost.
- The retry lives ONLY in `_probe_status`, the single live-probe classification point shared by the sync carry-over drop path and the `compare` check failure path (one-code-path rule). Callers that inject a `probe=` seam (hermetic replay, unit tests) bypass it entirely — recorded-fixture paths never retry and never sleep.
- The failure/keep text keeps naming the probe class that fired (`404/410` vs `gated`), so a reader of a red battery sees which class exhausted the budget.
- Tests extend the existing real-socket loopback harness: 404-then-200 → NOT dead; 404 across the full budget → dead; 401/403 → gated with exactly ONE request (no retry); transport-error-then-200 → NOT dead.

# Impact
- `scripts/gen_trending_quant_catalog.py` — `_probe_status` (retry budget), new constants `PROBE_ATTEMPTS`, `PROBE_RETRY_BACKOFF`
- `tests/test_quant_catalog_compare.py` — loopback harness scenarios for the retry rule
- Unchanged contracts: `make check-quant-catalog` (hermetic + LIVE=1), `make sync-quant-catalog` drop/keep lines, the injected-probe seams of `carry_over`/`compare`
- Spec delta: `quant-catalog-live-probe` (MODIFIED requirement)
