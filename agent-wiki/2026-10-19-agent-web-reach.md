# 2026-10-19 — the agent's masked web reach (#362)

Implements [#362](https://github.com/asimov-agent/llgenie/issues/362) (PR [#369](https://github.com/asimov-agent/llgenie/pull/369)),
a child of the bot-fleet parent
[#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change:
`openspec/changes/agent-web-reach`.

## What was wrong (measured)

`grep -rn FIRECRAWL .github/workflows Makefile scripts/` found nothing: the agent image installs the
Hermes CLI, that CLI carries the bundled `browser-firecrawl` plugin keyed by `FIRECRAWL_API_KEY`, and
no leg forwarded the key — so the capability was inert. A bot could not verify anything it cannot test
locally (an engine's repo, a release, a flag, a 404 link), and the failure mode is silent: with the
key present but stripped by Hermes's terminal filter, a fetch leg returns an empty result and the run
stays green.

## What changed

- `FIRECRAWL_API_KEY` joined `AGENT_SHELL_KEYS`, so `make agent-shell-keys-check` proves the agent's
  **own shell** sees it (the #358 seam, merged as #365).
- ONE fetch leg — `make agent-fetch URL=… OUT=…` — with a prompt that reads the key from the
  environment, forbids printing/echoing/writing the value, writes only the fetched markdown, and fails
  on 401/402/403. `api.firecrawl.dev` appears in exactly one prompt (a second hand-rolled fetch is the
  defect the suite checks for).
- `make search-smoke` + `scripts/fetch_smoke.py`: key by name, one request, `MAX_READ` cap, a `--budget`
  on the markdown that is kept and printed, 401/402/403 loud with the code, an HTTP 200 with no
  `data.markdown` refused, missing key exit 2, `--allow-unconfigured` the only opt-out.
- `tests/test_agent_web_reach.py` — 9 tests — drives the REAL client against a local
  `http.server` (the external system the test provides), never a stub of the code under test: 401,
  empty 200, a real body, the budget, the missing key, plus the by-name forwarding and the prompt rules.
- `tests/fixtures/host-only-wiring.json` records why `search-smoke` is human-run: the repo defines no
  `FIRECRAWL_API_KEY` secret yet and a missing key is exit 2 by design, so wiring it now would fail
  every bot job.

## Measured

```
$ pytest tests/test_agent_web_reach.py -q     -> 9 passed
$ make -n agent-fetch URL=https://example.com | grep -c _HERMES_FORCE_FIRECRAWL_API_KEY
1
```

## Decisions

- **The smoke is a local-server test, not a live one.** The Firecrawl call is an EXTERNAL system, and
  AGENTS.md allows the real client to be pointed at a server the test provides; the product code
  builds the request and the test asserts on the response handling. A live smoke needs the secret,
  which is why `host-only-wiring.json` carries the dated decision.
- **The budget bounds the markdown, not the socket read.** A truncated JSON cannot be parsed, so the
  read is capped at `MAX_READ` and the budget truncates `data.markdown` — measured while writing the
  budget test, which first failed because `--budget 100` sliced the JSON in half.
- **One leg only.** The suite fails if a second prompt names the scrape API, so the key rules cannot
  drift into a copy.

## Follow-ups

- Define the `FIRECRAWL_API_KEY` repository secret, then wire `make search-smoke` into the bot jobs
  beside `make agent-shell-keys-check` and delete the `host-only-wiring.json` entries (they go stale
  the moment CI reaches the target).
- #363 (loud missing key on every leg) and #364 (the issue-bot implementer's empty `GH_TOKEN`) remain.
