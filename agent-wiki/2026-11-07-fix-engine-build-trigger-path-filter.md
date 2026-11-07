# Fix-engine-build-trigger-path-filter: pin-bump trigger never finds its producer (issue #2041)

## What was wrong

The `engine-build-pr-trigger` "will" arm (issue #1633) filtered the GitHub run-list with
`.path == "/.github/workflows/engine-build.yml"` — a leading slash the REST API never returns (it
reports `.path == ".github/workflows/engine-build.yml"`). So `_existing_run_ids()` always returned
∅, the discovery loop never saw the producer it just dispatched, and DISPATCH_TIMEOUT (90 s)
fired with `run_id=""` → `[will] FAIL engine=…: run  concluded queued/None` (empty run id).
Repo-wide: **0 successes ever** (34 failures / 29 cancelled / 1 pending, workflow 405203031), while
every pin-bump PR like #1982 reds repeatedly and re-runs fail identically (run `42396610033`
attempt 2 also dispatched `42399388147` and still reported empty run id).

## What changed

- `scripts/engine_build_trigger.py:95` (`_existing_run_ids`) and `:191` (`_push_group_holder`):
  `.path == ".github/workflows/engine-build.yml"` (no leading slash) — matches the API's real shape.
- `tests/test_engine_build_trigger.py`: mock `.path` values corrected to the true shape (lines
  57/78/84), and `fake_gh_api` now applies the `.path == "…"` literal it is handed, so a
  re-introduced leading slash reds the suite instead of being encoded as correct.

## Verification

- 13/13 unit tests pass with the fix (repo pytest venv).
- Guard proven: with a leading-slash filter, the re-shaped mock returns ∅ ("new run not found");
  with the fix, the mock matches 2/2 and a live `_existing_run_ids("asimov-agent/llgenie","gh")`
  returns non-empty and includes the just-dispatched producer `42399388147`.
- Live API shape re-confirmed: `gh api .../actions/runs/42399388147 --jq .path` →
  `.github/workflows/engine-build.yml`.

## Status

This PR fixes the code this lane owns. It does NOT itself merge (owner flow, #1088); the fix lands
via the PR under `feat/fix-engine-build-trigger-path-filter`. Once on `main`, a re-run of a
pin-bump trigger (e.g. #1982) will finally find and await its producer.
