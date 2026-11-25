# pins-gate-ordering — Tasks

Issue: [#3051](https://github.com/asimov-agent/llgenie/issues/3051)

- [ ] 1. `scripts/check_engine_pins_published.py` gains the PR pending state: `PINS-PENDING <ref>` /
      `ALIAS-PENDING <ref>` + `PINS DEFERRED <n>` and exit 0 for cells THIS change repins, mode from
      `ENGINE_PINS_PR_PENDING` with a `GITHUB_EVENT_NAME == pull_request` fallback; `main`/`push`
      keeps `NOT PUBLISHED` + `[select]` + exit 1, a non-repinned gap and every `--all` sweep stay
      hard red whatever the event.
- [ ] 2. `scripts/engine_pins_await.py` + `make engine-pins-await` (`mk/engines.mk`): read-only await
      on the head's `engine-build-pr-trigger` run(s) via `gh api` (injectable `run_lookup`),
      `AWAIT <run_id> <status>` lines, bounded by `ENGINE_PINS_AWAIT_SECONDS` (default 0), exit 0 in
      every outcome, no dispatch/rerun/cancel, no-op green when nothing is repinned.
- [ ] 3. `.github/workflows/pipeline.yml` `unit` job (the job `ci.yml`'s `linux` lane calls; `ci.yml`
      has no `make ci-unit` step of its own): the `make engine-pins-await` step sits BEFORE the
      `make ci-unit` step, so the battery's pins step is evaluated after the lane's producer.
- [ ] 4. Tests: `tests/test_check_engine_pins_published.py` (pending green / main hard-red control /
      event fallback / committed sweep never defers / alias-pending) and new
      `tests/test_engine_pins_await.py` (polls-until-concluded, nothing-repinned no-op, never
      dispatches, pipeline.yml await-before-ci-unit ordering).
- [ ] 5. Docs in the same commit: `agent-wiki/2026-11-25-pins-gate-ordering-3051.md` naming issue
      #3051 and the PR, plus the `docs/changes.d/2026-11-25-pins-gate-ordering-3051.md` fragment, and
      `make changes-index` re-renders `CHANGES.md` from the fragments.
- [ ] 6. Verification measured at the head: `make lint check-wiring check-workflows check-docs
      openspec-tasks-check lane-preflight`, the named test modules, `make test-unit` with zero skipped,
      and `make openspec-validate NAME=pins-gate-ordering` — each replayable command rc=0 at the head
      sha.
