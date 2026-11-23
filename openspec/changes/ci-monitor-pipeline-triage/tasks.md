# Tasks: ci-monitor-pipeline-triage (issue #3019)

- [x] T1 `run_failure_reactor.py`: `--file-only` flag — Route-A head filed via the Route-B issue
      path (same marker dedupe, same `issue_body.render`, same labels, same supersession), dispatch
      path unreachable, verdict line names the override; `_fork_pr` never mislabels a same-repo
      `main` run as FIFTH-PARTY; in-tick filing memory (`_TICK_FILED`) dedupes one failure class
      across several routings in one process (GitHub search lags a just-filed issue). (proven:
      pytest tests/test_run_failure_reactor.py rc=0 incl.
      test_file_only_files_a_pushable_pr_failure_instead_of_dispatching +
      test_a_main_branch_run_is_never_labelled_a_fifth_party_fork +
      test_two_runs_of_one_failure_class_file_one_issue_per_tick)
- [x] T2 `ci_monitor.py`: `--triage` mode — same snapshot output; MAIN-RED routes its run id;
      PR-CHECKS resolves failed completed runs on the head sha through the fetch seam
      (`gh run list -c <sha>`); one `TRIAGE-*` verdict line per routing; `--dry` files nothing;
      MONITOR-OK/ERROR route nothing. (proven: pytest tests/test_ci_monitor.py rc=0 incl. 5 triage tests)
- [x] T3 `mk/bots.mk`: `ci-monitor-triage` target (`DRY=1` preview) + `FILE_ONLY=1` knob on
      `run-failure-reactor`; `Makefile` `.PHONY` entry. `package-layers.json`: no edge needed —
      `ci_monitor` and `run_failure_reactor` share the "Bots and automation" group.
- [x] T5 `agents/llgenie-planner/`: SOUL.md lane rule "The monitor tick is triage-first and never
      idles (issue #3019)" + cron prompt mirrored at `prompts/llgenie-ci-monitor.md`; live skill
      drift folded live→tree (p5js `export-frames.js`, `export-pipeline.md`, claude-code +
      simplify-code SKILL.md); `make sync-agent-profile PROFILE=llgenie-planner` rc=0. The AGENTS.md
      monitor-contract wording is out of scope (protected file, direct owner yes required) and is
      filed as #3022. (proven: sync-agent-profile rc=0, 966 files verified, 1 changed)
- [x] T6 Docs: `agent-wiki/2026-11-23-ci-monitor-triage-3019.md` + matching
      `docs/changes.d/` fragment + `make changes-index` + README `make ci-monitor-triage` target
      entry (docs census gate `tests/test_check_docs.py`). (proven: make changes-index rc=0,
      make check-docs rc=0)
- [x] T7 Verify: targeted pytest files rc=0; `make lint check-wiring check-docs` rc=0;
      `make openspec-validate NAME=ci-monitor-pipeline-triage` rc=0; full `make test-unit` rc=0;
      `make ci-monitor-triage DRY=1` rc=0 against live gh reads (prints plan, files nothing).
      (proven at head 0c5be99c676832a0e0267ba68c252fe083e3c4b7: pytest 48 passed targeted;
      lint/check-wiring/check-docs/changes-index/openspec-validate rc=0; make test-unit rc=0,
      4386 passed / 13638 deselected; make -s ci-monitor-triage DRY=1 rc=0, and live non-dry
      filed #3020)
