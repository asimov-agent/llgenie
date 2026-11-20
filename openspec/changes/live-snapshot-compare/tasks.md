# Tasks — live-snapshot-compare

- [x] build the snapshot pass: one read per compared live file recording size, mtime and sha256
      digest, wired into `check_agent_profiles.py` before the tree/live walk
- [x] render every live-side comparison (size, line-set, live-only) from the snapshot, never from a
      re-`stat()`/re-read of the live path
- [x] carry `live snapshot <sha12>` in each live finding detail and a snapshot manifest (file count +
      manifest digest) in the OK comparison line
- [x] pin the behaviour in tests: `test_a_live_file_mutated_after_the_snapshot_still_renders_the_snapshot`,
      `test_a_live_longer_finding_names_the_snapshot_it_measured`, the OK-line manifest pin
      `test_the_ok_comparison_line_names_the_snapshot_manifest`, and the existing red-1 / green-0 exit
      pins unchanged (`pytest tests/test_agent_profiles.py tests/test_skill_parity.py` 166 passed, rc=0)
- [x] land the wiki note (`agent-wiki/2026-11-20-live-snapshot-compare-2979.md`), the
      `docs/changes.d/` fragment and the `CHANGES.md` row (`make changes-index` wrote the row from
      935 fragments, `make check-docs` exit 0)
- [x] `make -s openspec-validate NAME=live-snapshot-compare` exits 0 and every task here is ticked
- [x] the whole unit battery runs green against the committed head (`make test-unit` exits 0)
      — proven: `make test-unit` rc=0 at committed head a1e43a6d1 (LANEQ_UNIT_RC=0, 2026-11-20)

Ship (not a task): push `feat/live-snapshot-compare-2979` after rebasing onto `origin/main` (the
cherry-picked `live-profile-mtime-stamp` commit drops out once PR #2980 merges), open the PR that
closes #2979, and drive it green and armed.
