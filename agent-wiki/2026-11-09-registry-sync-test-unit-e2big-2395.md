# 2026-11-09 — the registry-sync change path scopes the job secrets off its test-unit leg so the gh-spawning tests stop E2BIGing (issue #2395)

## The defect

The registry-sync change path ran `make test-unit` with the `sync` job's job-level
`HF_TOKEN`/`GITHUB_TOKEN` forwarded into the test container (`TEST_OPTS` passes
`-e HF_TOKEN -e GITHUB_TOKEN -e GH_TOKEN`). The gh-spawning tests
(`tests/test_bot_pr_tokens.py`, `tests/test_issue_implementer.py`) spawn a subprocess
with `issue_implementer._gh()`'s `env=dict(os.environ)`, so a large forwarded secret env
exceeded the kernel `ARG_MAX` and the spawn died deterministically with
`OSError: [Errno 7] Argument list too long`. Measured at `main=ffac22274` (runs
42608937982 and 42612274355, both `3 failed, 3500 passed`), the change path could never
reach a green `test-unit`, so the `Open / update the sync PR` leg (gated on the green
check set, issue #758) never fired and a genuine upstream registry change (the store's
`generated_utc` moved) left llgenie ranking from a stale copy.

Push CI's `linux / unit` runs the identical suite green precisely because its job
declares **no job-level secret env** — the runner's automatic `GITHUB_TOKEN` (the small
`github.token`, always set) is all the token the container sees, so the env stays small.
(An empty-string mask alone is NOT enough: `scripts/engine_bump_rebase.py` calls
`load_token()` at import and requires a NON-empty `GITHUB_TOKEN`/`GH_TOKEN` — an empty
string is falsy and breaks `tests/test_engine_bump_rebase.py`, measured on run
42669761035.)

## What changed

`.github/workflows/registry-sync.yml`: the change-path `make test-unit` step now re-points
the three forwarded vars at the step level — `HF_TOKEN` to an empty string (push CI's
unit job carries no Hub token) and `GITHUB_TOKEN`/`GH_TOKEN` to `${{ github.token }}` —
making this leg byte-identical to push CI's unit env: no job-level secret VALUE escapes,
and `engine_bump_rebase.load_token()` still finds a small non-empty token. The hermetic
checks and test-unit replay recorded Hub answers / use the tokens under test, so they
need no secret beyond the automatic one. No gate, check or permission is removed or
relaxed; the gh-spawning tests still run and still spawn the real fake `gh` binary.

## Verification

- Reproduced in the exact `ghcr.io/asimov-agent/llgenie/test:7df351360413` image: a
  large forwarded `HF_TOKEN` makes the same three tests die
  `OSError: [Errno 7] Argument list too long`, and with the env scoped small they pass
  (`3 passed`) — matching push CI's green.
- `scripts/check_workflows.py check` passes at the head.
- 2026-11-11: the temporary diagnostic (target `env-diag`, added for dispatch
  42956020030) was reverted at head `5fb4c7f63` — the dispatch ran `ref: main`, not the
  branch tree, so the diag never executed. The post-merge dispatch proof (green
  change-path `test-unit` + gated sync-PR leg) is lane **#2480** items 3-4; the
  acceptance criteria were re-scoped to the pre-merge head proof (3 suites pass in the
  fixed leg env shape at head). PR #2442 carries no `closes` keyword until that lane
  lands. PR: #2442.

Issue: #2395

