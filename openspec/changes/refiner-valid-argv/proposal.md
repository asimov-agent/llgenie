# The issue-refiner's pick must run, and a failed pick must be loud (issue #314)

**Issue:** [#314](https://github.com/asimov-agent/llgenie/issues/314)
**Capability:** `refiner-pick-reliability`

## Why

The refiner has never refined an issue, and every run reports SUCCESS.

`scripts/issue_refiner.py::_thread()` builds argv the real CLI rejects — `--comments` together with
`--json`:

```
$ make issue-refiner-pick REPO=asimov-agent/llgenie
[issue-refiner] gh issue view 91 --repo asimov-agent/llgenie --comments --json number,title,body,state,author,labels,comments failed (1): specify only one of --comments or --json
```

This is the same argv class fixed for the implementer in #268; the `comments` field is already
requested through `--json`, so `--comments` is invalid AND redundant. The crash is in every scheduled
run (e.g. [38818619593](https://github.com/asimov-agent/llgenie/actions/runs/38818619593)).

It was invisible because `issue-refiner.yml`'s pick step runs under `set +e` and writes
`action=${action:-unknown}` -> `picked=false` -> every later step is skipped and the run is green.
A crashed decision and "nothing to pick" are indistinguishable (the shared rule is #312).

## What Changes

- **`scripts/issue_refiner.py`** — `_thread()` drops `--comments` and keeps
  `--json number,title,body,state,author,labels,comments` (verified live: the `comments` JSON field
  returns the bodies).
- **`.github/workflows/issue-refiner.yml`** — the pick step captures the sweep's exit code and fails
  LOUDLY on non-zero, instead of reporting `action=unknown` and a green no-op.
- **`tests/test_issue_refiner.py`** — the fake `gh` REFUSES `--comments` with `--json` (as the real
  CLI does), so the pre-fix pick fails the suite; new tests pin the argv and the loud-failure guard.

## Impact

The refiner starts picking an issue instead of no-oping; a future crash in the pick turns the run red.

## Not covered

- #311 — the same workflow's undefined `secrets.OPENROUTER_API_KEY` / `OPENCODE_API_KEY`.
- #312 — the shared decision-loudness rule across the other bot workflows.
