# pins-gate-ordering — Tasks

Issue: [#3051](https://github.com/asimov-agent/llgenie/issues/3051)

- [x] 1. `scripts/check_engine_pins_published.py` gains the PR pending state: `PINS-PENDING <ref>` /
      `ALIAS-PENDING <ref>` + `PINS DEFERRED <n>` and exit 0 for cells THIS change repins, mode from
      `ENGINE_PINS_PR_PENDING` with a `GITHUB_EVENT_NAME == pull_request` fallback; `main`/`push`
      keeps `NOT PUBLISHED` + `[select]` + exit 1, a non-repinned gap and every `--all` sweep stay
      hard red whatever the event. (proven: `pytest tests/test_check_engine_pins_published.py -q` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5; live contrast rc=2 with `[select]` rows under main semantics vs rc=0 with 4 x `PINS-PENDING` + `PINS DEFERRED 4` under `ENGINE_PINS_PR_PENDING=1`, same unpublished re-pin)
- [x] 2. `scripts/engine_pins_await.py` + `make engine-pins-await` (`mk/engines.mk`): read-only await
      on the head's `engine-build-pr-trigger` run(s) via `gh api` (injectable `run_lookup`),
      `AWAIT <run_id> <status>` lines, bounded by `ENGINE_PINS_AWAIT_SECONDS` (default 0), exit 0 in
      every outcome, no dispatch/rerun/cancel, no-op green when nothing is repinned. (proven: `pytest tests/test_engine_pins_await.py -q` rc=0 and `GITHUB_REPOSITORY=asimov-agent/llgenie ENGINE_PINS_AWAIT_SECONDS=30 make engine-pins-await` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5, printing `[await] repinned engine(s): ollama` then `no engine-build-pr-trigger.yml run for this head; nothing to await`)
- [x] 3. `.github/workflows/pipeline.yml` `unit` job (the job `ci.yml`'s `linux` lane calls; `ci.yml`
      has no `make ci-unit` step of its own): the `make engine-pins-await` step sits BEFORE the
      `make ci-unit` step, so the battery's pins step is evaluated after the lane's producer. (proven: `make check-workflows` rc=0 and the `test_the_await_step_runs_before_the_battery_in_pipeline_yml_unit_lane` case rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5, which reads the `unit` job's step list and refuses `make ci-unit` before `make engine-pins-await`)
- [x] 4. Tests: `tests/test_check_engine_pins_published.py` (pending green / main hard-red control /
      event fallback / committed sweep never defers / alias-pending) and new
      `tests/test_engine_pins_await.py` (polls-until-concluded, nothing-repinned no-op, never
      dispatches, pipeline.yml await-before-ci-unit ordering). (proven: `pytest tests/test_engine_pins_await.py tests/test_check_engine_pins_published.py -q` rc=0, 66 passed, 13 await cases, at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5)
- [x] 5. Docs in the same commit: `agent-wiki/2026-11-25-pins-gate-ordering-3051.md` naming issue
      #3051 (its landing PR is the `closes #3051` reference on this branch's PR), plus the `docs/changes.d/2026-11-25-pins-gate-ordering-3051.md` fragment, and
      `make changes-index` re-renders `CHANGES.md` from the fragments. (proven: `make check-docs` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5 — 381 user-facing targets documented, 965 fragments index every agent-wiki/ note; `make check-package-layers` rc=0 — 190 modules in 5 groups, 81 cross-group edges stated, 0 cycles)
- [ ] 6. Verification measured at the head: `make lint check-wiring check-workflows check-docs
      openspec-tasks-check lane-preflight`, the named test modules, `make test-unit` with zero skipped,
      and `make openspec-validate NAME=pins-gate-ordering` — each replayable command rc=0 at the head
      sha.
