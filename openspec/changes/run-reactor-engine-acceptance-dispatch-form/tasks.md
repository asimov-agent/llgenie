# Tasks — run-reactor-engine-acceptance-dispatch-form

- [x] `scripts/run_failure_reactor.py::issue_body`: an `ENGINE_LANE` failure's acceptance criterion 1
      renders "the failing cell is green in a real run of the failing cell, with its own log
      recorded" (`is_engine = lane == ENGINE_LANE`), and never "green locally on this host".
- [x] `scripts/check_pr_acceptance.py`: an unticked LOCAL_BUILD criterion's finding appends the
      dispatch form (`DISPATCH_FORM` / `local_build_hint`), so the implementer sees the right
      restatement in the gate log.
- [x] Regression test `tests/test_run_failure_reactor.py::test_an_engine_build_acceptance_names_the_dispatch_run_never_a_local_build`
      FAILS on the pre-change "green locally on this host" wording and PASSES on this branch.
- [x] Regression test `tests/test_check_pr_acceptance.py::test_unticked_local_build_criterion_points_at_the_dispatch_form`
      FAILS on the pre-change finding and PASSES on this branch.
- [x] Reactor + acceptance suites green: `tests/test_run_failure_reactor.py` +
      `tests/test_check_pr_acceptance.py` all pass (75 tests total).
- [x] Gate suite green: `make lane-preflight` prints `preflight: OK (6 gates)`.
- [x] Openspec validation: `make openspec-validate NAME=run-reactor-engine-acceptance-dispatch-form`
      exits 0.
- [x] Docs trio: `agent-wiki/2026-11-09-run-reactor-engine-acceptance-not-local-build.md` +
      `docs/changes.d/…` row + regenerated `CHANGES.md`; no engine image built anywhere.
