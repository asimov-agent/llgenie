# issue-dedupe's JEV preflight failure names itself and is tracked once per class

Issue [#802](https://github.com/asimov-agent/llgenie/issues/802). OpenSpec change
`issue-dedupe-jev-preflight`. PR: opened by the issue-bot from this tree (the job writes the body from
`pr-body.md`).

## What was measured

`gh run view 40702295009 --log-failed` (and 40697636784) gave one line for both runs:

```
[require-env] FATAL: TYPESAFE_API_KEY is missing or empty — refusing to start.
make: *** [Makefile:661: agent-jev-preflight] Error 2
```

The 06:20Z run that "succeeded" had the preflight step **skipped** (`conclusion: skipped` on that
step): the sweep picked no pair, so the job never reached the step whose secret was missing. The first
run with a pair to compare failed in its preflight, and the duplicate sweep decided nothing while
`gh issue list --search 'JEV'` found no tracker.

Cause: `issue-dedupe.yml`'s `dedup` job set `NOUS_API_KEY` and `REPO` only, while
`make agent-jev-preflight NERVE_REQUIRE=1` refuses to start without `TYPESAFE_API_KEY` (the #363 guard
in front of the leg).

## Decisions

- **The exit status stays red.** `make jev-preflight-required` keeps the preflight's non-zero exit; the
  change is that the failure now explains itself and has one work item. Softening it to green would
  let a bot run with the decision layer off, which the maintainer's rule forbids.
- **One tracker per class, not per run.** The marker `<!-- jev-preflight: <class> -->` is the body's
  first line and is searched back with `gh issue list --search`. A repeat failure prints the existing
  number and files and comments nothing — the issue is the class's memory, not a run log.
- **Classes are read from the preflight's own words**, so a class is evidence, not a guess. The nine
  signatures live in one table with the fix for each; an unrecognised failure is `unknown`.
- **The body goes through `scripts/issue_body.py`**, and the tracker is registered in
  `issue_body.PRODUCERS` in the same change, so `make check-issue-bodies` sees it.
- **Only CI writes.** The Makefile passes `--local` whenever `GITHUB_ACTIONS` is not `true`, and the
  tracker then prints the class and the fix and makes no `gh` call. This is a defect found while
  verifying: a local `make jev-preflight-required` on this Docker-less host filed a real `unknown`
  tracker (#809) for a precondition that was the host's, not the repository's. #809 was closed with
  the reason and the label removed; the behaviour is locked by
  `test_a_local_run_reports_and_writes_nothing`.
- **The key reaches the leg's container too.** `issue-dedup`'s `docker run` now forwards
  `-e TYPESAFE_API_KEY`, as `issue-refiner`'s does: the job-level secret reaches only the HOST step,
  so without it the decision leg itself still ran with the layer off. Locked by
  `test_the_dedupe_leg_receives_the_provider_key_like_the_refiner_does`.
- **The exit status is preserved exactly** (`exit $$rc`), not flattened to 1: the step's code is
  evidence, and #802 asks for a clear message, not a different failure.

## Verification (real output)

- `python3 -m pytest tests/test_jev_preflight_tracker.py -q` → 10 passed.
- `python3 -m pytest` over the new file plus the suites it touches (`test_issue_dedup`, `test_issue_body`,
  `test_check_issue_body`, `test_workflows_valid`, `test_check_docs`, `test_wiring`,
  `test_lint_linefeeds`, `test_script_exit_codes`) on the host python → 94 passed in 39.56s. The full
  `make test-unit` suite is containerized and could not run here; CI is where it is read.
- `python3 scripts/jev_preflight_tracker.py classify --log <the real failing output>` →
  `class=key-missing` with the measured line and the fix.
- `--dry` report against `asimov-agent/llgenie`: prints the class, the fix and the issue it would file,
  and the marker search (the real `gh issue list --search`, read-only) returns nothing.
- `make check-wiring`, `make check-docs`, `make check-issue-bodies`, `make check-workflows`,
  `make check-pr-hygiene`, and `python3 scripts/lint_linefeeds.py` → green.

## Not verified here, and why

This sandbox cannot build or start a container (`unshare: operation not permitted` even with a running
daemon and the legacy builder), so the legs that run INSIDE the agent image — `make
agent-jev-preflight NERVE_REQUIRE=1` with the engine active, `make issue-dedup` producing a decision,
and therefore a green `issue-dedupe` run — could not be executed. `make lint`, `make test-unit` and
`make openspec-validate` are containerized for the same reason. #802 therefore stays open (the PR does
not close it) until a green `issue-dedupe` run cites its duplicate decision.
