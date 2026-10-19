# 2026-10-19 — the credential reaches the AGENT's shell (issue #358)

Implements [#358](https://github.com/asimov-agent/llgenie/issues/358) (PR [#365](https://github.com/asimov-agent/llgenie/pull/365)),
the first child of the bot-fleet parent [#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change:
`openspec/changes/agent-shell-keys`.

## What was wrong (measured, this host)

Hermes strips provider credentials from its terminal tool on purpose
(`tools/environments/local_env_policy.py::_STATIC_PROVIDER_ENV_BLOCKLIST` holds `NOUS_API_KEY`,
`GH_TOKEN`, `FIRECRAWL_API_KEY`, `HF_TOKEN`), so llgenie's `-e NOUS_API_KEY` reached the container
and the Hermes process while the **agent's shell read it EMPTY** — the failure the sibling repo
measured as HTTP 401 on every search leg with the job green. llgenie carried six legs forwarding
plain names, no `_HERMES_FORCE_` anywhere, and no check. Reproduced against the real Hermes with
sentinel values: plain → `agent-shell=EMPTY` (exit 1); forced twin → `agent-shell=set` (exit 0).

## What changed

- **Makefile**: ONE `AGENT_SHELL_KEYS` list (`NOUS_API_KEY GH_TOKEN HF_TOKEN TYPESAFE_API_KEY`),
  host-only export of `_HERMES_FORCE_<NAME>` from `<NAME>` by reference (nothing re-created under
  `/.dockerenv`), `AGENT_SHELL_FORWARD` / `AGENT_SHELL_FORWARD_PLAIN`, and `$(AGENT_SHELL_FORWARD)`
  on all seven agent legs.
- **`scripts/agent_shell_keys_check.py`**: drives Hermes's real `LocalEnvironment`, prints lengths
  only, exits 1 when a container credential reads empty in the agent's shell, 2 for a missing key or
  a missing Hermes; `--allow-unconfigured` is the only opt-out.
- **`make agent-shell-keys-check`** (public, runs inside the agent image) + `_agent-shell-keys-check`
  (internal); `AGENT_SHELL_CHECK_KEYS=` narrows the list per job.
- **Workflows**: `fix-bot.yml` (3 keys), `issue-bot.yml` / `issue-refiner.yml` / `rebase-bot.yml`
  (2 keys each) run the check before their agent work, each with the exact key set its job provides.
- **`tests/test_agent_shell_keys.py`** in `make test-unit`: list coverage, by-name forwarding
  (sentinels never in `make -n`), the host export and the container no-op, the loudness + opt-out,
  and the wiring to the four bot workflows.
- **AGENTS.md** "A bot's credential must reach the AGENT's shell, never a log" + **README** section.

## Verified

- `python3 -m pytest tests/test_agent_shell_keys.py -q` → 7 passed.
- Real Hermes RED/GREEN with sentinels (commands in the README section); `make -n
  agent-shell-keys-check` renders the four `-e _HERMES_FORCE_*` names and no value.
- `make check-wiring`, `make check-docs`, `make check-secret-output`, `make lint`,
  `make check-workflows`, `make check-dispatch-forms`, `make openspec-validate NAME=agent-shell-keys`.

## Decisions

- The live probe's gate is the **bot jobs' step**, not a new PR-triggered job: a `pull_request` run
  cannot pull an agent image a push run has not published yet (#155), and the four bot jobs already
  build/pull that image.
- **No key value moved**: the same names travel the same way, plus a name-only twin; `HF_TOKEN` and
  `GH_TOKEN` are in the list because `_STATIC_PROVIDER_ENV_BLOCKLIST` strips them too, so an agent
  that needs `gh` or a Hub call is exactly as blind without the twin.

## Follow-ups filed

- The issue-bot implementer's job sets no `GH_TOKEN`, so `-e GH_TOKEN` on that leg forwards an empty
  value — the agent's `gh` calls run unauthenticated. Filed as [#364](https://github.com/asimov-agent/llgenie/issues/364) (a child of #357).
- Next child: #359 (redacted Hermes run log + artifact), then #360/#361 (secret guards), #362 (the
  masked web reach — it depends on this seam), #363 (loud missing key on every leg).
