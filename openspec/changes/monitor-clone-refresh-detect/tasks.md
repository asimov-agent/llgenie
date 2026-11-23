# monitor-clone-refresh-detect — tasks

- [x] T1 Land `scripts/host_ci_monitor_wrapper.py`: repo-canonical wrapper whose `_ensure_clone()`
      checks clone/fetch/merge exit codes and reports a dirty tree; broken refresh prints
      `MONITOR-ERROR clone-refresh-failed` (detail on stderr); make's stderr passes through in every
      outcome; clone/remote paths overridable via `LLGENIE_MONITOR_CLONE`/`LLGENIE_MONITOR_UPSTREAM`.
      (proven: write rc=0, lint rc=0)
- [x] T2 Hermetic tests `tests/test_host_ci_monitor_wrapper.py`: fetch-fail, dirty clone, green
      passthrough, pre-target clone still prints `make-ci-monitor-failed`, green stderr passthrough —
      local-path git remotes, fake Makefiles, zero network.
      (proven: pytest tests/test_host_ci_monitor_wrapper.py rc=0, 5 passed)
- [x] T3 `make host-ci-monitor-install` target (`mk/bots.mk`), `.PHONY` entry, README entry.
      (proven: make lint rc=0, make check-wiring rc=0 — 492 documents, 189 scripts)
- [x] T4 Run `make host-ci-monitor-install` on this host and prove byte-identical hashes of the repo
      copy and every installed copy; verify the live monitor clone refreshes to current main.
      (proven: make host-ci-monitor-install rc=0, 3 copies one sha256 57a082c4…; clone HEAD bc75f93fa
      == origin/main, porcelain 0; live wrapper run rc=0 → 13-line snapshot, empty stderr)
- [x] T5 Narrow the tick contract's carve-out: the cron job prompt (and, once the #3019 prompt mirror
      is on main, `agents/llgenie-planner/prompts/llgenie-ci-monitor.md`) treats
      `MONITOR-ERROR clone-refresh-failed` as an alarm to fix the clone, and reads
      `MONITOR-ERROR make-ci-monitor-failed` as "not landed" only when the clone is current.
      (proven: cron edit 857ee38c40ce rc=0 (new carve-out in job prompt, old sentence gone); mirror
      updated on PR #3023 branch at c4b2a391a)
- [ ] T6 Docs: `agent-wiki/` entry + `docs/changes.d/` fragment + `make changes-index`;
      `make openspec-validate NAME=monitor-clone-refresh-detect` rc=0.
- [ ] T7 Verify: full `make test-unit` rc=0 at the branch tip; `make lane-preflight` prints
      `preflight: OK`; live wrapper run prints a real snapshot.
