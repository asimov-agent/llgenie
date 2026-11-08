# Tasks

- [x] `scripts/engine_build_trigger.py` detects a 404 run-id poll (empty / non-JSON read) and re-resolves the run through the run-LIST endpoint keyed by `head_sha`+`branch` (the trigger knows the branch it dispatched) instead of treating the 404 as "not concluded" and waiting out `wait_min`.
- [x] `_dispatch_and_wait` concludes SUCCESS from the head_sha re-resolved run (a producer that already concluded success is reported immediately, never waited out to the bound), recording the resolved run id in the OK line.
- [x] `last_was_404` is tracked on the awaited-run return and the expiry message names a 404 visibility race (`never became visible (last poll 404) … poll visibility race, not a concluded build failure`) distinctly from a real-conclusion expiry (`never concluded, last status …`).
- [x] Regression test `test_404_poll_is_reresolved_by_head_sha_to_success` drives a 404 run-id poll + a head_sha list read answering real success with a far `--wait-min` and asserts rc 0 + the resolved run id named; on the pre-fix code it fails (fixed with the code, verified green).
- [x] Regression test `test_404_visibility_is_named_on_expiry` drives a never-visible 404 with `--wait-min 0` and asserts the 404-race phrasing in stderr.
- [x] Existing `tests/test_engine_build_trigger.py` battery stays green (15 passed: 13 prior + 2 new).
- [x] `make test-unit`, `make lint`, `make check-wiring`, `make check-docs` stay green on the PR.
- [x] Docs per convention: `docs/changes.d/` entry + `agent-wiki/` dated note + `CHANGES.md` row in the PR, all naming `#2059`.
- [x] PR carries `closes #2059`; `make lane-preflight` green and `make openspec-validate NAME=engine-build-trigger-404-reresolve` passes (validated structurally: each requirement carries WHEN/THEN, each scenario has Given/When/Then and a `- **Test:**` line).
