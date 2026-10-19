# The masked web reach runs in CI, on the repository secret

## Why

#362 (merged as #369) built the masked fetch leg and its smoke, but **no job ever ran them**: the
repository defined no `FIRECRAWL_API_KEY` secret, so `make search-smoke` was recorded in
`tests/fixtures/host-only-wiring.json` as a human-run target (#381). A capability that only a human
with a local key can exercise is not a check — the day the key is revoked, nothing says so.

Measured on `main@ab641b4` (2026-10-19):

```
$ gh api repos/asimov-agent/llgenie/actions/secrets --jq '.secrets[].name'   # before this change
BUMP_TOKEN
HF_TOKEN
NOUS_PORTAL_API_TOKEN
TYPESAFE_API_KEY
```

## What Changes

- **The secret exists** (`FIRECRAWL_API_KEY`, defined on the repository 2026-10-19 by the owner), so
  the targets can run where they are used.
- **ONE scheduled job** (`.github/workflows/search-smoke.yml`, daily 07:11 UTC + a hand dispatch for the
  owner/collaborators, behind the shared trigger guard) proves the reach: the agent's own shell is shown
  to see the key (`make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY`, #358) and then
  `make search-smoke` makes one real, bounded request. The key travels by NAME (`docker run -e` + the
  `_HERMES_FORCE_` seam); no step prints, echoes or interpolates its value.
- **The host-only record is deleted**: `tests/fixtures/host-only-wiring.json` no longer claims
  `search-smoke` is human-run, and `make check-wiring` (which fails a recorded exception CI reaches) is
  the proof.
- **The README's dispatch table and the web-reach section** state where it runs and on what.

## Impact

- Affected specs: `agent-web-reach` (the deployment half).
- Affected code: `.github/workflows/search-smoke.yml` (new), `tests/fixtures/host-only-wiring.json`,
  `tests/test_agent_web_reach.py`, `README.md`.
- No behaviour change to the leg itself: the same target, run by a job instead of by hand.

## Not covered (each its own issue)

- Wiring the fetch into a **bot prompt** (so a bot verifies an issue's claim mid-run) and the coverage
  report: #380.
- Rotating the key: a human action on the provider + the GitHub secret.
