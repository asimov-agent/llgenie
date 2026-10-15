# Tasks

- [x] 1. `claim_comment` writes `ttl=<minutes>m` and `run=<id>` into the marker (optional on parse, so a legacy marker still reads), and builds the human sentence from the same TTL in the honest unit
- [x] 2. `occupied()` ages a claim by the TTL its own marker announced, with the caller's value as the legacy fallback
- [x] 3. `run_is_live(gh_call, run_id)` + the `is_live=` hook: a claim whose run is `completed` releases the subject; an unreadable state is `None` and never releases
- [x] 4. `released()` names the holder and why it is gone; `cancelled` joins the release words
- [x] 5. All four bots claim with `ttl` + `GITHUB_RUN_ID` and read with a cached `is_live=` probe, printing the takeover
- [x] 6. Tests: the marker/announced-TTL/liveness/release contract in `tests/test_bot_claims.py`, the refiner's marker assertion updated; `85 passed` across the five bot suites in `llgenie/test:latest`
- [x] 7. Falsified: the new protocol tests fail on the pre-fix `scripts/bot_claims.py` (`8 failed, 6 passed`)
- [x] 8. README's claim section names the four bots, the marker's terms and the release-on-dead-run; `agent-wiki/2026-10-15-claim-lifecycle.md` records the work; `make lint`/`check-docs`/`check-wiring`/`openspec-validate` exit 0
