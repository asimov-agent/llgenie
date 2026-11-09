# registry-sync-test-unit-e2big — scope the job secrets off the change-path test-unit leg so the gh-spawning tests stop E2BIGing (issue #2395)

## Why

The registry-sync change path runs `make test-unit` with the `sync` job's job-level
`HF_TOKEN`/`GITHUB_TOKEN` forwarded into the test container (`TEST_OPTS` passes
`-e HF_TOKEN -e GITHUB_TOKEN`). The gh-spawning tests (`tests/test_bot_pr_tokens.py`,
`tests/test_issue_implementer.py`) spawn a subprocess with `issue_implementer._gh()`'s
`env=dict(os.environ)`, so a large forwarded secret env exceeds the kernel `ARG_MAX` and
the spawn dies deterministically with `OSError: [Errno 7] Argument list too long`
(measured at `main=ffac22274`, runs 42608937982 and 42612274355, both
`3 failed, 3500 passed`). Because `test-unit` can never go green, the `Open / update the
sync PR` leg — correctly gated on the green check set (issue #758) — never fires, so a
genuine upstream registry change leaves llgenie ranking from a stale store.

Push CI's `linux / unit` runs the identical suite green precisely because its job declares
**no job-level secret env**: the runner's automatic `GITHUB_TOKEN` (the small `github.token`,
always set) is all the token the container sees, so the container env stays small. An
empty-string mask alone is not enough — `scripts/engine_bump_rebase.py` calls `load_token()`
at import and needs a NON-empty `GITHUB_TOKEN`/`GH_TOKEN` (an empty string is falsy; measured
on run 42669761035 breaking `tests/test_engine_bump_rebase.py`).

## What Changes

`.github/workflows/registry-sync.yml`: the change-path
`make check-registry + check-quant-catalog + engine-skill-gap report + test-unit` step now
re-points the three forwarded vars at the step level — `HF_TOKEN` to an empty string (push
CI's unit job carries no Hub token), `GITHUB_TOKEN` and `GH_TOKEN` to
`${{ github.token }}` — making this leg byte-identical to push CI's unit env: no job-level
secret VALUE escapes, and `engine_bump_rebase.load_token()` still finds a small non-empty
token. The hermetic checks and test-unit replay recorded Hub answers / use the tokens under
test, so they need no secret beyond the automatic one. No gate, check or permission is
removed or relaxed; the gh-spawning tests still run and still spawn the real fake `gh`
binary.

## Capabilities

- **registry-sync-test-unit-e2big**: the registry-sync change path reaches a green
  `make test-unit` under the forwarded-secret env, then opens the sync PR.

## Impact

No check weakening, no skipped test, no permission change. The secrets remain job-level
(issue #1594) and are simply not forwarded by value into this one hermetic step's subprocess
env (re-pointed at the automatic small token).
