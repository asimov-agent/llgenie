# Tasks

- [x] 1. Write the proposal + spec for the queued-run alarm (issue #254).
- [x] 2. `scripts/queued_run_alarm.py`: find jobs queued longer than the threshold, report them
      with their runner label and age, exit 0/1/2, and comment at most once per run.
- [x] 3. `.github/workflows/queued-alarm.yml`: twice-an-hour schedule + manual dispatch, no
      conditional job (issue #107), PAT from a secret.
- [x] 4. `tests/test_queued_run_alarm.py` (real script, stub `gh` on PATH): the stuck/age
      threshold, the ignored states, the red exit, the once-per-run comment, the GitHub failure,
      and the label reporting.
- [x] 4b. Fill a missing label from the job's own REST object (`actions/jobs/<id>`), because
      `gh run view --json jobs` can leave `labels` empty — and the label is what tells a
      maintainer WHICH runner is missing. A failed detail lookup never loses the job.
- [x] 5. Wire the test into the test recipes and add `make queued-alarm` as the local entry point.
- [x] 6. Verify: the alarm suite green, `make lint`, `make check-wiring`, the workflow parses,
      and `make openspec-validate NAME=queued-run-alarm` valid.
- [x] 7. Commit as one atomic change, push, and open the PR (it does not close #254: the runner
      decision is still the maintainer's).
