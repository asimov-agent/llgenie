# The masked web reach is deployed: a bot leg uses it, and the URLs are checked

## Why

#362 (merged as #369) built the reach — `make agent-fetch` (one leg, key by name, never printed) and
`make search-smoke` (a dead key dies loudly) — and **no bot leg ever called either**. Measured on
`main@2e04fa3`:

```
$ grep -rn 'agent-fetch' .github/workflows/     # 0 hits
$ grep -n 'web-coverage' Makefile               # nothing
```

So the capability was unreachable from a run: a bot asked to verify an external claim (a release URL, a
version, a 404 link) still had no sanctioned, masked way to look, and nothing said which URLs the bots
depend on. `check-wiring` cannot see this — it requires a *document* to reach CI, and a make target no
job calls is green as long as a test or a README line names it.

## What Changes

- **`scripts/web_evidence.py`** — one seam, three modes: `list` (the candidate URLs named in an issue),
  `check` (one line per URL with its HTTP status, non-zero on a dead one — no model, no key), and
  `fetch` (pre-fetch each with the **real** `make agent-fetch`, capped, writing `fetched/index.md`).
  A `401/403` is reachable, not dead; a read that failed is recorded as UNKNOWN, never as false.
- **`make issue-evidence`** — the host leg that reaches the fetch. A bot leg runs INSIDE the agent
  image, so it cannot nest a container and call `agent-fetch` directly; the host pre-fetches instead.
- **`make issue-refiner` consumes it** — first `make agent-shell-keys-check
  AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY` (#358: the key must reach the AGENT's shell), then
  `make issue-evidence`, then the review. `issue-refiner.yml` forwards `FIRECRAWL_API_KEY` by name and
  covers it in the job's keys check; the review prompt reads `fetched/index.md` as evidence.
- **`make web-coverage`** — the declared dependency list (`tests/fixtures/bot-facing-urls.md`, or
  `ISSUE_FILE=`) checked deterministically, run daily by `search-smoke.yml`.
- **A derived wiring assertion** (`tests/test_agent_web_reach.py`, in `make test-unit`): closing the
  workflow targets over the Makefile's call graph must reach `agent-fetch`, so "the leg exists" can
  never again be mistaken for "the leg is used".

## Impact

- Affected specs: `agent-web-reach` (the deployment half of #362).
- Affected code: `scripts/web_evidence.py` (new), `tests/fixtures/bot-facing-urls.md` (new),
  `Makefile` (`web-coverage`, `issue-evidence`, the refiner leg, `.PHONY`), `.github/workflows/issue-refiner.yml`,
  `.github/workflows/search-smoke.yml`, `tests/test_agent_web_reach.py`, `.gitignore`, `README.md`.
- Cost: one model call per pre-fetched URL (capped at 3 per bot run); `web-coverage` costs no model call.

## Not covered (each its own issue)

- The implementer leg could pre-fetch the same way; the refiner is the first consumer and the shape is
  now shared, so extending it is a small follow-up rather than new design.
- `macos / top-tier` reds a PR on a live-Hub `TimeoutError`: #399.
