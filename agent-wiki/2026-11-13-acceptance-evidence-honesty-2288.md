# acceptance evidence honesty: ticks are judged by live run conclusions (issue #2288)

`check_pr_acceptance.py` accepted any tick carrying `proven: ... run=<digits>`
without consulting the cited run's conclusion: re-measured live 2026-11-13 over
all 1305 closed issues, 311 ticked criteria cite `run=<id>`; **178 of them,
across 46 closed issues, cite a run whose live conclusion is NOT green** (41
runs: 40 `failure`/`cancelled`, 1 unreadable 404 — `43073777356`) — a gate that
green-lights "proven" ticks backed by red CI (issue #2288).

Change (OpenSpec `acceptance-evidence-honesty`), three seams:

- **Gate** (`scripts/check_pr_acceptance.py`): `live_run_state(gh, repo, run)`
  reads `[status, conclusion, head_sha]` via `gh api` once per invocation
  (per-invocation cache, `main()`-scoped). A ticked criterion citing
  `run=<id>` is judged by that lookup: red conclusion → blocking
  `tick-cites-red-run`; unreadable (404/empty) → blocking
  `tick-run-unreadable`; green but belonging to another head than the judged
  revision → blocking `tick-stale-head-unflagged`; still `in_progress` →
  non-red `acceptance-proven-awaiting-writer`. `--gh`/`--rev` thread the
  lookup and the measured head through `acceptance_verdict`.
- **Seam** (`scripts/acceptance_writeback.py`): `tick_acceptance` refuses a
  verdict-ref with no 7–40 hex head sha (`HEAD_SHA_REF` grammar floor —
  decimal-only refs name no measured tree), and the `writeback` command calls
  `assert_runs_green` BEFORE the body fetch and the PATCH: every cited run
  must be `completed`/`success` at the ref's own head. `apply`/`check` stay
  offline with the same floor.
- **Finalizer** (`scripts/review_finalize.py`): `verdict_ref_runs_ok` runs
  before `tick_acceptance`; a red, unreadable, or wrong-head cited run makes
  `finalize` exit 2 with no write issued, `--dry` included.

Tests: hermetic fake-`gh` shims (sidecar `runs.json`/`issue.json`, argv logged
to `calls.log`) refuse each new finding class and prove the refusal happens
BEFORE any fetch or PATCH; 108 tests pass across `test_check_pr_acceptance.py`
+ `test_acceptance_writeback.py` + `test_review_finalize.py`. Closed issues
whose ticks cite red runs get append-only audit addendum comments; bodies are
never rewritten (#1644 append-only convention).
