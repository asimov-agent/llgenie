# Tasks

- [x] 1. `scripts/hf_auth.py` owns `rate_limit_wait`: `t` from `RateLimit`, else 300s, capped at 600s
- [x] 2. `_hf_get` and `_hub_json` call that function on 429, retry twice, and reset the count on any non-429
- [x] 3. Tests call the same function for the expected sleep (header, five-minute default, ten-minute cap, reset, both callers)
- [x] 4. README states that every Hub 429 uses this one wait
- [x] 5. `make openspec-validate NAME=hub-429-retry` exits 0
- [x] 6. `scripts/hf_auth.hub_open` is the one Hub GET: authorize, the shared 429 wait, two retries, reset on a non-429
- [x] 7. The size lookup, the ranged chunk download and the preflight probe call `hub_open` instead of `urlopen`
- [x] 8. Tests drive those three paths and assert the sleep against `rate_limit_wait`; `make test-unit` names the test file
- [x] 9. README names `hub_open` as the GET every download uses
- [x] 10. `make openspec-validate NAME=hub-429-retry` exits 0
