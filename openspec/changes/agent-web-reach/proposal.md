# agent-web-reach — proposal

Issue: [#362](https://github.com/asimov-agent/llgenie/issues/362) (child of [#357](https://github.com/asimov-agent/llgenie/issues/357))

## Why

llgenie's bots cannot reach the live web. The Hermes CLI they run on ships a bundled **Firecrawl**
plugin (measured on the same CLI the agent image installs: `hermes plugins list` lists
`browser-firecrawl | enabled | 1.0.0 | Firecrawl … FIRECRAWL_API_KEY`), the agent image installs that
CLI — and **`FIRECRAWL_API_KEY` was forwarded by nothing in this repo**, so the capability was inert:

```
$ grep -rn 'FIRECRAWL' .github/workflows Makefile scripts/     # no hits
```

A bot asked to verify something it cannot test locally — an engine's repo URL, an upstream release or
flag, a version in an issue, a 404 link — had no sanctioned, masked way to look, and the one failure
mode that matters is silent: with the key present but stripped by Hermes's terminal filter, a fetch
leg would return an empty result and the run would stay green (the sibling repo measured exactly that:
HTTP 401 on every search leg while the job was green, its issue #359).

## What Changes

- **`FIRECRAWL_API_KEY` joins the ONE list** (`AGENT_SHELL_KEYS`), so `make agent-shell-keys-check`
  proves the **agent's own shell** can see it — the seam #358 built (#365, merged).
- **ONE fetch leg**: `make agent-fetch URL=… OUT=…` runs `hermes -z` inside the agent image with a
  prompt that reads the key from the ENVIRONMENT (never interpolated into the prompt), states that
  the value is never printed/echoed/written, writes only the fetched markdown to `OUT`, and fails on
  401/402/403 instead of inventing content.
- **`make search-smoke`** + **`scripts/fetch_smoke.py`**: one real request with a bounded response,
  the key read by name, `401/402/403` loud with the code, an HTTP 200 with no `data.markdown` refused
  (a fetch leg must not report success on nothing), and a missing key exit 2 naming the variable.
  `--allow-unconfigured` is the only opt-out and no workflow uses it.
- **`tests/test_agent_web_reach.py`** (9 tests, `make test-unit`): the key is in the list and the leg
  forwards it BY NAME (a sentinel never appears on a command line); the prompt reads the variable and
  forbids printing it, and it is the only prompt that mentions the API; the smoke is driven by the
  REAL client against a local server — 401 fails with the code, an empty 200 is refused, a real body
  succeeds and the value is printed nowhere, and the budget bounds what is kept.
- **`AGENTS.md`** (a web reach is one leg, keyed by name), **`README.md`**, **`agent-wiki/`**.

## Impact

- A bot can now verify an external claim without ever exposing the key: the value travels only
  through the environment, the console shows at most the fetched text, and the leg's transcript is
  covered by #359's redaction seam when that lands.
- `search-smoke` cannot run in CI yet: the repo has no `FIRECRAWL_API_KEY` secret, and a missing key
  is exit 2 by design. The decision is recorded in `tests/fixtures/host-only-wiring.json` (dated,
  with the reason) rather than hidden; wiring it into the bot jobs is the follow-up once the secret
  exists.
- Out of scope, filed separately: the key's rotation, and porting the sibling's whole refresh
  pipeline (raw JSON -> merge -> validate -> render an index) — llgenie consumes the vendored
  registry and has no index of its own.
