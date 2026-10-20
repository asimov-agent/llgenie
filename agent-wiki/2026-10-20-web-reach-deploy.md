# The masked web reach is deployed: a bot leg uses it, and the URLs are checked

Issue #380 (follow-up of #357 / #362). OpenSpec change: `web-reach-deploy`. PR: #402.

## What was wrong

#362 built `make agent-fetch` and `make search-smoke` and no bot leg called either:

```
$ grep -rn 'agent-fetch' .github/workflows/     # 0 hits
$ grep -n 'web-coverage' Makefile               # nothing
```

So the reach was unreachable from a run — a bot still could not verify an external claim — and nothing
said which URLs the bots depend on. `check-wiring` cannot catch it: it requires a *document* to reach
CI, and a make target no job calls stays green while a test or a README line names it.

## The architectural constraint (why the host pre-fetches)

`agent-fetch` is a **host** target: it starts the agent image and runs `hermes -z` inside it (one model
call). A bot leg already runs *inside* that image, so it cannot nest a container and call `agent-fetch`
itself. Owner's decision on #380: the **host pre-fetches** the URLs an issue names before the agent
starts, and the agent reads the fetched text as evidence.

## What changed

- `scripts/web_evidence.py` — one seam, three modes: `list` (candidates from an issue's prose), `check`
  (one line per URL with its HTTP status, non-zero on a dead one; no model, no key) and `fetch`
  (pre-fetch each through the **real** `make agent-fetch`, capped at 3, writing `fetched/index.md`).
  A `401/403` is reachable, not dead; a read that failed is recorded as UNKNOWN, never as false.
- `make issue-evidence` — the host leg that reaches the fetch.
- `make issue-refiner` — now: agent-shell credential check (`AGENT_SHELL_CHECK_KEYS=FIRECRAWL_API_KEY`),
  then `make issue-evidence`, then the review; the prompt reads `fetched/index.md`.
- `make web-coverage` — the declared list (`tests/fixtures/bot-facing-urls.md`, or `ISSUE_FILE=`),
  run daily by `search-smoke.yml`.
- The derived wiring assertion in `tests/test_agent_web_reach.py`.

## Verification

- `make web-coverage` → 4/4 reachable, one line each; a 404 URL exits non-zero and names it.
- `pytest tests/test_agent_web_reach.py` → 16 passed (the wiring assertion, the gate order, extraction,
  the dead-URL failure, the 401/403 classifier).
- `make check-wiring`, `make check-docs`, `make check-workflows`, `make check-secret-output`,
  `make check-dispatch-forms`, `make lint`, `make openspec-validate NAME=web-reach-deploy`,
  `make test-unit`.

## Honest limits

- The pre-fetch costs one model call per URL and is capped at 3 per refiner run; `web-coverage` is
  keyless and free.
- The refiner is the first consumer; the implementer leg can reuse the same target later.
- The ignored `fetched/` tree is written into the checkout the leg runs in. `make loop`'s rename guard
  reads gitignored files (#350) — if that guard flags `fetched/`, it is #350's defect surfacing, not a
  new one.
