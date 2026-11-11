# check-docs change→note gate (#1123): a behavioural change owes a docs note

Gate: `make check-docs`, invoked as a step of the `scope` CI job. Read the job log, not the lane's report.

Failure shape:

```
[check-docs] ERROR: change->note: this branch changes <file> but adds no agent-wiki/<stem>.md note — a behavioural change owes a note (and its docs/changes.d/<stem>.md row); see issue #1123
[check-docs] 1 problem(s); see `make docs-report`
make: *** [Makefile:1001: check-docs] Error 1
```

## Rule

A behavioural change to `scripts/*.py` owes **two** artifacts: `agent-wiki/<stem>.md` and `docs/changes.d/<stem>.md`. Lanes routinely assert "no docs trio owed" because the diff is "only" a script + test — the gate refutes that every time. Verify with the log line before repeating the claim.

The fix is additive: add the note + fragment (and regenerate any fragment census), do **not** touch the gate.

## Measurement

```bash
gh pr view <n> --json statusCheckRollup --jq '[.statusCheckRollup[]|"\(.name): \(.status)/\(.conclusion)"]|.[]'
gh api repos/asimov-agent/llgenie/actions/runs/<scope_run>/jobs \
  --jq '[.jobs[]|select(.name=="scope").steps[]|select(.conclusion=="failure")|"\(.number): \(.name)"]|join("\n")'
gh api repos/asimov-agent/llgenie/actions/jobs/<job_id>/logs --allow-escape-sequences \
  > /tmp/sl.bin && sed 's/\x1b\[[0-9;]*m//g' /tmp/sl.bin | grep -iE 'check-docs|ERROR|Error 1'
```

## Related: stale base reds check-pr-base in the same run

Both reds co-occur when a lane branches and then waits: the branch falls behind `origin/main`, so `guard` step `make check-pr-base` fails (`merge-base must be the base itself`) and `scope` step `make check-docs` fails on a changed file lacking a note. Diagnose both from the same run before dispatching, and dispatch them as one correction on one vehicle (rebase onto current `origin/main` + add the note), never two.
