# 2026-10-15 — issue #314: the issue-refiner's pick runs again, and its failure is loud

Part of the "exercise every bot dispatcher one at a time" sweep. Exercising `issue-refiner.yml`
showed the refiner had **never refined an issue**, while every run reported SUCCESS.

## What was done

- OpenSpec change `refiner-valid-argv` created FIRST via the containerized CLI (`make openspec-new`),
  validated, all tasks ticked.
- `scripts/issue_refiner.py`: `_thread()` no longer passes `--comments` alongside `--json` — `gh`
  refuses that pair ("specify only one of --comments or --json"), which killed `pick` on every run
  (the #268 class, fixed for the implementer but not here). The comment bodies come from the
  `comments` JSON field alone.
- `.github/workflows/issue-refiner.yml`: the pick step captures the pick's exit code and exits 1 on a
  non-zero one, so a crashed decision is never again reported as `action=unknown` + a green no-op.
- `tests/test_issue_refiner.py`: the fake `gh` now REFUSES `--comments` with `--json` exactly as the
  real CLI does; two new tests pin the argv and the workflow's loud-failure guard.

## Verified

- `tests/test_issue_refiner.py` in `llgenie/test:latest` (`:ro`): **19 passed**.
- Rule 6c: the 2 new tests FAIL on the pre-fix tree (`2 failed, 17 deselected`) and pass after.
- Live: `make issue-refiner-pick REPO=asimov-agent/llgenie` now RUNS and picks
  (`[issue-refiner] picked #91 …; refine-in.md written`, `action=pick`) where it previously crashed
  with `specify only one of --comments or --json`. (The live run also posted its normal claim comment
  on #91; a claim with no `done` ages out on the protocol's own TTL.)
- `make lint`, `make openspec-validate NAME=refiner-valid-argv`, `make check-wiring`,
  `make check-docs` green.

## Status

- Branch `fix/refiner-valid-argv`, PR against `asimov-agent/llgenie:main`, `closes #314`.
- Related, NOT covered here: #311 (the same workflow's undefined `secrets.OPENROUTER_API_KEY` /
  `OPENCODE_API_KEY`) and #312 (the shared decision-loudness rule across the other bot workflows).
