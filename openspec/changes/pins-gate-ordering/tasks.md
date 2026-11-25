# pins-gate-ordering — Tasks

Issue: [#3051](https://github.com/asimov-agent/llgenie/issues/3051)

- [x] 1. `scripts/check_engine_pins_published.py` gains the PR pending state: `PINS-PENDING <ref>` /
      `ALIAS-PENDING <ref>` + `PINS DEFERRED <n>` and exit 0 for cells THIS change repins, mode from
      `ENGINE_PINS_PR_PENDING` with a `GITHUB_EVENT_NAME == pull_request` fallback; `main`/`push`
      keeps `NOT PUBLISHED` + `[select]` + exit 1, a non-repinned gap and every `--all` sweep stay
      hard red whatever the event. (proven: `pytest tests/test_check_engine_pins_published.py -q` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5; live contrast rc=2 with `[select]` rows under main semantics vs rc=0 with 4 x `PINS-PENDING` + `PINS DEFERRED 4` under `ENGINE_PINS_PR_PENDING=1`, same unpublished re-pin)
- [x] 2. `scripts/engine_pins_await.py` + `make engine-pins-await` (`mk/engines.mk`): read-only await
      on the head's `engine-build-pr-trigger` run(s) via `gh api` read through `scripts/proc.py`
      (injectable `run_lookup`),
      `AWAIT <run_id> <status>` lines, bounded by `ENGINE_PINS_AWAIT_SECONDS` (default 0), exit 0 in
      every outcome, no dispatch/rerun/cancel, no-op green when nothing is repinned. (proven: `pytest tests/test_engine_pins_await.py -q` rc=0 and `GITHUB_REPOSITORY=asimov-agent/llgenie ENGINE_PINS_AWAIT_SECONDS=30 make engine-pins-await` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5, printing `[await] repinned engine(s): ollama` then `no engine-build-pr-trigger.yml run for this head; nothing to await`)
- [x] 3. `.github/workflows/pipeline.yml` `unit` job (the job `ci.yml`'s `linux` lane calls; `ci.yml`
      has no `make ci-unit` step of its own): the `make engine-pins-await` step sits BEFORE the
      `make ci-unit` step, so the battery's pins step is evaluated after the lane's producer. (proven: `make check-workflows` rc=0 and the `test_the_await_step_runs_before_the_battery_in_pipeline_yml_unit_lane` case rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5, which reads the `unit` job's step list and refuses `make ci-unit` before `make engine-pins-await`)
- [x] 4. Tests: `tests/test_check_engine_pins_published.py` (pending green / main hard-red control /
      event fallback / committed sweep never defers / alias-pending) and new
      `tests/test_engine_pins_await.py` (polls-until-concluded, nothing-repinned no-op, never
      dispatches, pipeline.yml await-before-ci-unit ordering). (proven: `pytest tests/test_engine_pins_await.py tests/test_check_engine_pins_published.py -q` rc=0, 108 passed with the 4 pins-verdict cases, measured at this lane's head)
      (`tests/test_engine_pins_await.py` now holds 16 cases: 13 seam cases, the two API-row cases that caught the
      display-name-vs-`path` lookup bug measured live against run 45242589764, and the case that pins the
      subprocess-policy rule of item 11)
- [x] 5. Docs in the same commit: `agent-wiki/2026-11-25-pins-gate-ordering-3051.md` naming issue
      #3051 (its landing PR is the `closes #3051` reference on this branch's PR), plus the `docs/changes.d/2026-11-25-pins-gate-ordering-3051.md` fragment, and
      `make changes-index` re-renders `CHANGES.md` from the fragments. (proven: `make check-docs` rc=0 at head 32c9907ca5b2ec03e3dec824ccea0c289ac681b5 — 381 user-facing targets documented, 965 fragments index every agent-wiki/ note; `make check-package-layers` rc=0 — 190 modules in 5 groups, 81 cross-group edges stated, 0 cycles)
- [x] 6. Verification measured at the head: `make lint check-wiring check-workflows check-docs
      openspec-tasks-check lane-preflight`, the named test modules, `make test-unit` with zero skipped,
      and `make openspec-validate NAME=pins-gate-ordering` — each replayable command rc=0 at the head
      sha. (measured at head 1f32eaee5da91dad440551f6edd88c7387a255f5: `make test-unit` rc=0, 4460
      passed / 13638 deselected / 0 skipped in 1024.35 s; `make lint check-wiring check-workflows` rc=0;
      `make check-package-layers` rc=0, 190 modules and 81 stated cross-group edges; `make check-docs`
      rc=0, 381 user-facing targets documented and 965 fragments indexing every agent-wiki/ note;
      `pytest tests/test_engine_pins_await.py tests/test_check_engine_pins_published.py
      tests/test_package_layers.py tests/test_check_docs.py -q` rc=0, 107 passed; live seam read rc=0
      printing `[await] PRODUCER 45242589764 already completed/failure` and `AWAIT DONE 1 producer
      run(s) concluded`.)
- [x] 11. The await's GitHub reads go through the ONE subprocess policy seam. The lane's first CI red
      was `[ci_unit] FAILED step 28/54: make check-proc-gate (rc=2)`, naming
      `scripts/engine_pins_await.py:59: proc = subprocess.run(["gh", "api", path], …)`: issue #797
      confines `subprocess.run/check_output/Popen` in `scripts/` to `scripts/proc.py` or a
      `# proc-allow:` line, and new code joins the seam instead of joining the tracked exemption
      list. `_gh_api` now calls `proc.run_ok` (never raises on a non-zero exit; the seam names the
      command's stderr itself) under `GH_API_TIMEOUT_SECONDS = 60.0`, so a hung read is a `WARN` the
      pins gate decides past rather than a wedge; the cross-group import is stated in
      `scripts/package-layers.json` with the issue #797 reason. (proven: `make check-proc-gate` rc=0
      printing `[proc-gate] OK: every subprocess.run/check_output/Popen in scripts/ … is in
      scripts/proc.py or on a # proc-allow: line`, `pytest tests/test_engine_pins_await.py
      tests/test_check_engine_pins_published.py -q` rc=0 with 69 passed including
      `test_the_seam_reads_gh_through_the_subprocess_policy_module`, and `make check-package-layers`
      rc=0, all at this lane's head)
