# ci-verdict-superseded-rows-2885 — Tasks

Issue: [#2885](https://github.com/asimov-agent/llgenie/issues/2885)

- [x] 1. New `scripts/head_check_rows.py`: `superseded_ids(rows, blocking, file_of)` groups a head's
      check-run rows by (job name, workflow file) and marks every strictly-older CONCLUDED row of a
      group superseded (ordered by `started_at`/`completed_at`, tie-broken by row id); unconcluded rows
      neither supersede nor are superseded; rows whose workflow file is unresolvable never supersede and
      are never superseded; the file resolver is only paid for groups that hold a blocking row.
      Verified: `tests/test_head_check_rows.py` 8/8 pass.
- [x] 2. `scripts/ci_verdict.py::unjudged_reds` filters candidates through the shared collapse before
      reporting blockers and prints each cleared row as a `superseded red (not a block)` note. Pinned
      parity (`UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS`), the TRANSIENT exemption, and the
      judged-roster exclusion untouched. Verified: full `tests/test_ci_verdict.py` green + three new
      supersede tests.
- [x] 3. `scripts/auto_merge.py`: `_check_runs` projects `id`/`started_at`; new `_workflow_file` mirrors
      `ci_verdict.workflow_of` (run-read cached, `""` when unreadable — conservative); `failing_checks`
      blocks only on non-superseded reds and notes each cleared row with its run id. Verified: full
      `tests/test_auto_merge.py` 113/113 green including three new supersede tests (merge-on-superseded,
      defer-on-newest-red, defer-when-newer-row-unfinished).
- [x] 4. `scripts/package-layers.json`: `head_check_rows` joins the "CI entrypoints" group (the same
      group `ci_verdict` lives in, so no edge is needed for its import — the gate forbids same-group
      edge entries); the cross-group `auto_merge -> head_check_rows` edge carries the one-rule reason.
      Verified: `make check-package-layers` rc=0 (171 modules, 63 edges, 0 cycles).
- [x] 5. Docs: `CHANGES.md` fragment under `changes.d/`, a concise header note in
      `.github/workflows/ci-verdict.yml` (newest concluded row owns the head), and an `agent-wiki/` entry
      naming issue #2885 and the PR.
- [x] 6. Verification you can tick the moment the work is done: the full unit battery
      `make test-unit` rc=0 (4005 passed); `make -s ci-verdict REPO=asimov-agent/llgenie
      RUN_ID=44059191405` rc=0 — replay of fold PR #2882's CI run at head `b08fb844` prints the
      dead scope row of run 44059151877 as `superseded red (not a block)` and concludes `success`;
      `make openspec-validate NAME=ci-verdict-superseded-rows-2885` exits 0.
