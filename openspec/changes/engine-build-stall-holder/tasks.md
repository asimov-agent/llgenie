# Tasks

- [x] 1. `openspec/changes/engine-build-stall-holder` — proposal + `specs/engine-build-stall-holder/spec.md` (G/W/T, a `- **Test:**` line per scenario) + this checklist, written before the code
- [x] 2. `scripts/engine_build_trigger.py` — detect a `pending`/`queued` awaited run and read the in-progress push-group holder (`_push_group_holder`)
- [x] 3. `scripts/engine_build_trigger.py` — name the holder in the FAIL line, flag **STALLED**, warn a re-dispatch queues behind the same gate
- [x] 4. `tests/test_engine_build_trigger.py` — held-run names the holder; pending-with-no-holder stays a plain failure
- [x] 5. Run `tests/test_engine_build_trigger.py` + engine-build sibling suites (23 pass) + lint; arm after all-green
