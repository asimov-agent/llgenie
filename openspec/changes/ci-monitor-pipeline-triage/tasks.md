# Tasks: ci-monitor-pipeline-triage (issue #3019)

- [x] T1 `run_failure_reactor.py`: `--file-only` flag — Route-A head filed via the Route-B issue
      path (same marker dedupe, same `issue_body.render`, same labels, same supersession), dispatch
      path unreachable, verdict line names the override; `_fork_pr` never mislabels a same-repo
      `main` run as FIFTH-PARTY. (proven: pytest tests/test_run_failure_reactor.py
      rc=0 incl. test_file_only_files_a_pushable_pr_failure_instead_of_dispatching +
      test_a_main_branch_run_is_never_labelled_a_fifth_party_fork)
- [x] T2 `ci_monitor.py`: `--triage` mode — same snapshot output; MAIN-RED routes its run id;
      PR-CHECKS resolves failed completed runs on the head sha through the fetch seam
      (`gh run list -c <sha>`); one `TRIAGE-*` verdict line per routing; `--dry` files nothing;
      MONITOR-OK/ERROR route nothing. (proven: pytest tests/test_ci_monitor.py rc=0 incl. 5 triage tests)
- [x] T3 `mk/bots.mk`: `ci-monitor-triage` target (`DRY=1` preview) + `FILE_ONLY=1` knob on
      `run-failure-reactor`; `Makefile` `.PHONY` entry. `package-layers.json`: no edge needed —
      `ci_monitor` and `run_failure_reactor` share the "Bots and automation" group.
- [ ] T5 `AGENTS.md` monitor contract: planner-profile monitor job, triage-first tick, no-idle
      pacing while a lane's CI runs, fix-the-failed-PR-pipeline-on-its-branch rule;
      `agents/llgenie-planner/` SOUL/prompts folded to match (live↔tree), `make
      sync-agent-profile PROFILE=llgenie-planner` rc=0.
- [ ] T6 Docs: `agent-wiki/2026-11-23-ci-monitor-triage-3019.md` + matching
      `docs/changes.d/` fragment + `make changes-index`.
- [ ] T7 Verify: targeted pytest files rc=0; `make lint check-wiring check-docs` rc=0;
      `make openspec-validate NAME=ci-monitor-pipeline-triage` rc=0; full `make test-unit` rc=0;
      `make ci-monitor-triage DRY=1` rc=0 against live gh reads (prints plan, files nothing).
