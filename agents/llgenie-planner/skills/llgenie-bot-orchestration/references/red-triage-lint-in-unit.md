# Triaging a red PR: read the failing STEP, never the job name

## `linux/lint` + `linux/unit` red together is usually ONE root cause

Symptom: a PR reds on both `linux / lint` and `linux / unit`, and the unit job's
log says "N passed" with no failing test. The "unit" red is the shared **lint
step inside ci-unit**, not a test assertion. Root cause in practice: new files
(change notes under `agent-wiki/` or `docs/changes.d/`, and anything else
`write_file` created) ended without a trailing newline; `lint_linefeeds.py`
named them in the scope job's log as `LINT FAIL — files missing a trailing
newline`.

Repair is one commit, same vehicle: append `\n` to each named file, verify
`lint_linefeeds.py` reports `LINT OK — all tracked text files end with a
newline` and `check_docs.py check` passes, push to the existing branch. Never
open a second PR for it.

## A `linux / unit` red whose FAILING STEP is `check-pr-base` is stale-base, not a test failure

`make ci-unit` runs `check-pr-base` at the END (Makefile `ci-unit` target), so a branch cut from a
stale base reds the whole `linux / unit` job with exit 2 and **no failing test** — the unit tests
all pass, the job still reads FAILURE. Symptom in the job log:

```
[check-pr-base] FAILED: `HEAD` is NOT cut from `origin/main` — its merge-base with `origin/main`
is `<sha>`, not `origin/main` itself ... (issue #845).
make: *** [Makefile:1778: ci-unit] Error 2.
```

Do not route this to an implementer as a product/unit defect and do not open a new PR. Confirm the
root cause is the base (grep the log for `check-pr-base`), then the fix is a rebase onto the LIVE
`origin/main` fetched right before the rebase — see `rebase-and-ambient-red.md`. A lane that says
"unit in_progress" while the rollup already reads `COMPLETED/FAILURE` is quoting a stale run; read
the per-check `status`/`conclusion` at the head (see `gh-api-measurement-traps.md` §3).

## A guard failing in under ~15s is a base/scope gate, not a broken test

`guard` → `make check-pr-base` fails in ~11s when the branch was cut from an
older `main` (merge-base must be the base itself). A lane reporting "unit test
broken" while the run died that fast is describing the wrong job. Fix is a
rebase onto freshly fetched `origin/main` — branch from the sha fetched in that
moment, `--force-with-lease` + `--force-if-includes` — never a fresh PR, never a
push while a run at the head is in progress.

## Read the steps, not the names

```bash
gh api "repos/<owner>/<repo>/actions/runs/<run_id>/jobs?per_page=100" \
  --jq '[.jobs[]|select(.conclusion=="failure")|"\(.name): \([.steps[]|select(.conclusion=="failure")|.name]|join(","))"]|.[]'
```

Also: `gh run list` prints `run_number`, not the API run id — passing it to
`/actions/runs/<id>` 404s. Resolve the real id with
`gh api ".../actions/runs?per_page=40" --jq '[.workflow_runs[]|select(.head_sha|startswith("<sha8>"))|.id]'`.

## A `ci-verdict` red while a selected leg is still `in_progress` is not a main red

`ci-verdict` publishes "no decision" when it fires before a selected job
concludes. Check `status` of every job before calling main red; 9/10 green with
one `in_progress` leg is a transient, re-verify when that leg completes.
