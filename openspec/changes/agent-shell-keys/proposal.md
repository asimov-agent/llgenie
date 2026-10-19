# agent-shell-keys — proposal

Issue: [#358](https://github.com/asimov-agent/llgenie/issues/358)

## Why

Every bot leg hands the agent image its credentials as a plain `-e NAME`, and **nothing proves the
NAME reaches the agent's own shell**. Hermes strips provider credentials from its terminal tool on
purpose (its `tools/environments/local_env_policy.py` blocklist), so a key is present in the
container, visible to the `make` recipe that started it — and **empty** in the environment of the
command the agent actually runs. The one sanctioned way through is the `_HERMES_FORCE_<NAME>` form,
which the terminal env builder unwraps back to `<NAME>`.

Reproduced on this host against the real Hermes the agent image installs:

```console
$ NOUS_API_KEY=SENTINEL HF_TOKEN=SENTINEL python3 scripts/agent_shell_keys_check.py NOUS_API_KEY HF_TOKEN
[agent-shell-keys] NOUS_API_KEY: container=set agent-shell=EMPTY (MISMATCH; _HERMES_FORCE_NOUS_API_KEY NOT forced; value never printed)
[agent-shell-keys] HF_TOKEN:     container=set agent-shell=EMPTY (MISMATCH; _HERMES_FORCE_HF_TOKEN NOT forced; value never printed)
rc=1
$ NOUS_API_KEY=SENTINEL HF_TOKEN=SENTINEL _HERMES_FORCE_NOUS_API_KEY=SENTINEL _HERMES_FORCE_HF_TOKEN=SENTINEL \
    python3 scripts/agent_shell_keys_check.py NOUS_API_KEY HF_TOKEN
[agent-shell-keys] OK: 2 credential(s) visible in the agent's shell.
rc=0
```

The sibling repo measured the consequence first (its issue #359): the key was in the container, the
step log read `FIRECRAWL_API_KEY: ***`, and the agent's `curl` sent an EMPTY Bearer — every search
leg got HTTP 401 while the job was green. llgenie has the same plumbing and none of the proof: six
agent legs forward `-e NOUS_API_KEY` / `-e TYPESAFE_API_KEY` / `-e GH_TOKEN`, there is no
`AGENT_SHELL_KEYS` list, no `_HERMES_FORCE_` anywhere, and no `agent-shell-keys-check` target. The
one proof it does run (`make agent-jev-preflight`) executes a `make` recipe **inside** the container —
it proves what `docker run` forwarded, which is exactly what was NOT in question.

## What Changes

- **One list, one seam (Makefile)**: `AGENT_SHELL_KEYS` names every credential a container receives
  (`NOUS_API_KEY`, `GH_TOKEN`, `HF_TOKEN`, `TYPESAFE_API_KEY`); on the host, `make` exports
  `_HERMES_FORCE_<NAME>` from `<NAME>` by reference — the value never appears on a command line, in a
  recipe or in a log — only when `<NAME>` is set, and inside a container (`/.dockerenv`) nothing is
  re-created so the check proves what `docker run` forwarded. Every agent leg forwards the forced
  names by NAME.
- **`scripts/agent_shell_keys_check.py`**: drives **Hermes's real terminal environment**
  (`LocalEnvironment`, the code the agent's `terminal` tool uses) inside the agent image and fails,
  naming the variable, when a key that IS set in the container reads empty in the agent's shell. It
  prints LENGTHS only — never a value, never a prefix. No stand-in, no re-implementation of Hermes's
  filter. A key that is unset in the container, or a Hermes that cannot be found, is a LOUD failure
  (exit 2) — a skipped credential check is the defect this change closes; `--allow-unconfigured` is
  an explicit local opt-out that says so.
- **Two targets**: `_agent-shell-keys-check` (internal, runs the script) and `agent-shell-keys-check`
  (public, runs it inside the agent image through `$(RUNTIME) run`).
- **The bot jobs run it** — `.github/workflows/fix-bot.yml`, `issue-bot.yml`, `issue-refiner.yml`,
  `rebase-bot.yml`: one step before the agent work, so a job whose credential cannot reach the agent
  stops in seconds instead of after a 120-180 minute-timeout run. The key names the jobs already set
  (`NOUS_API_KEY` from `NOUS_PORTAL_API_TOKEN`, `GH_TOKEN` from `BUMP_TOKEN`, `TYPESAFE_API_KEY`) stay
  exactly as they are; no new secret is introduced and no value is added anywhere.
- **`make test-unit`**: `tests/test_agent_shell_keys.py` (hermetic) proves the list names every
  credential a leg forwards, the forced names travel by NAME (a `make -n` with sentinels set must not
  contain a sentinel), `make` really exports the forced name from the plain one (and nothing inside a
  container), and the target is wired to a workflow CI runs.
- **`AGENTS.md`**: the durable rule — a credential reaches the agent's shell only through
  `AGENT_SHELL_KEYS` + the `_HERMES_FORCE_` seam; forwarding the plain name proves nothing.
- **README.md** and **`agent-wiki/2026-10-19-agent-shell-keys.md`**: the navigation entry and the work
  record.

## Impact

- The bot jobs gain one step (seconds) and stop being silently keyless.
- No key value is added or moved: the same names travel the same way, plus a name-only twin.
- The seam is the precondition for the masked web reach (#362): a search leg whose key is stripped is
  green with an empty result, which is the failure mode this change closes first.
- Out of scope, filed separately: the engine-bump/registry-sync workflows commit as identities outside
  the allowlist (#353) and the refiner's `DRY=1` preview writes into the tree (#352) — unrelated
  defects, not touched here.
