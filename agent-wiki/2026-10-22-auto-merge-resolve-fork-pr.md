# A finished fork run is resolved back to its PR

Issue: #508. PR: #509.

Auto-merge run `39735179724` (triggered by CI run `39732261968`, fork PR #506) failed in "Resolve the pull
request the finished run belongs to" before `make auto-merge` ever ran:

```
gh: Not Found (HTTP 404)
resolved PR #{
  "message": "Not Found", ... "status": "404"
}
##[error]Invalid format '  "message": "Not Found",'
```

`gh api` writes a 404's error **body to stdout**, and `|| true` drops only the exit status — so the JSON
became `$number`, the `[ -z ]` guard never fired, the fork fallback from #504 stayed unreachable, and the
multi-line blob broke `$GITHUB_OUTPUT`. Every agent PR lives in the fork, so every one of them was stuck.

The resolution now lives in `scripts/resolve_run_pr.py` behind `make auto-merge-resolve`: a value is a PR
number only when it is digits, the run object is tried first and the owner-scoped head search second,
nothing resolving exits non-zero naming the run and the head, and the result is the single line
`number=<n>`. `auto-merge.yml` calls the target (no inline `gh`), so CI and the host run the same code,
and `tests/test_resolve_run_pr.py` pins the 404 fall-through, the owner scoping, the loud failure and the
one-line output against a real fake `gh` binary on disk.

Verified: `pytest tests/test_resolve_run_pr.py` → 7 passed. The old inline snippet reproduced the measured
multi-line `$GITHUB_OUTPUT` blob against the same fake `gh`; the new target wrote exactly `number=506`.
