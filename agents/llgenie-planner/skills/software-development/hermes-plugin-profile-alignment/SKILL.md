---
name: hermes-plugin-profile-alignment
description: "Use when aligning a Hermes plugin across all profiles."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hermes, plugins, profiles, audit, alignment, nerve, verification]
    related_skills: [hermes-agent, hermes-plugin-development]
---

# Hermes plugin ↔ profile alignment audit

## When to Use

Use when the user asks any of:

- "verify plugin X is installed/enabled in all my profiles"
- "are my profiles aligned with the default?"
- "is this plugin fully set up?" (across more than one home)
- after installing or updating a user plugin on a multi-profile machine

Do **not** answer from `hermes plugins list` alone. That command lies in a specific,
reproducible way. This skill is the procedure that produces a real answer.

## The core trap: plugins are per-home, not per-machine

A user plugin resolves from `get_hermes_home()/plugins`. So:

- A plugin installed in `~/.hermes/plugins/` is **invisible to every named profile**.
- Each profile needs its own copy under `~/.hermes/profiles/<p>/plugins/`.
- `hermes plugins list` (with or without `HERMES_HOME`/`-p`) happily reports the plugin as
  `enabled` from `plugins.enabled: [...]` in that home's config **even when the plugin
  directory is missing or unresolvable there**. Reporting is config-driven, not resolution-driven.

Never accept `plugins list` as proof of installation. Two tests are authoritative:

1. `hermes plugins doctor <plugin-id> --ci` — name-based resolution; actually discovers,
   parses the manifest, imports, and registers. Fails loudly when the dir/id is wrong.
2. A real PTY session (see "Live probe" below) plus the load line in that home's
   `logs/agent.log`.

## Trap 2: the plugin directory must be named after the plugin id

A plugin is discovered two different ways, and they disagree when the directory name is wrong:

- **Directory scan** (session load): walks `plugins/*/`, reads each manifest, uses the
  manifest's `name:` as the id. Works even if the dir is named `hermes-nerve` while the
  manifest says `name: nerve`.
- **Name-based resolution** (`plugins doctor`, `plugins enable`, `plugins update`): looks for
  `<home>/plugins/<id>`. A mismatch makes the plugin **load fine in real sessions while
  `doctor` reports `ERROR: ... is not an installed plugin id`**.

So "it works when I chat" does not mean the install is correct. Rename the directory to match
`name:` in `plugin.yaml`. Symptom to watch for: `doctor` error mentioning a path in a
*different* home than the one you targeted.

## Trap 3: `.install-metadata.json` is installer-owned provenance

`<home>/plugins/.install-metadata.json` records `{<id>: {pinned, revision, source, catalog?}}`.
It is what `plugins update` consults. If a plugin directory was copied/renamed by hand, the
metadata goes stale — e.g. it still names a **different plugin** entirely, so `update` targets
a plugin that isn't there and never touches the real one. Verify per home that the metadata key
set equals the directory set, and that `revision` matches `git -C <dir> rev-parse HEAD`.

## Trap 4: Kanban env vars poison the plugin at session launch

If any of `HERMES_KANBAN_TASK`, `HERMES_KANBAN_TASK_ID`, `HERMES_KANBAN_BOARD` is set when a
session starts, plugins that branch on worker mode load differently. Nerve is the canonical
example: it hides all 16 tool schemas and runs `headless_worker=True` (`tools=0` in the load
line). The value is often just the session id, so it looks innocuous.

This is **per-session, not per-home** — the same home will show both `tools=16` and `tools=0`
in its log history. Do not mistake it for a misconfiguration. When running any probe, strip the
vars first:

```bash
env -u HERMES_KANBAN_TASK -u HERMES_KANBAN_TASK_ID -u HERMES_KANBAN_BOARD \
    -u HERMES_CRON_SESSION -u HERMES_GATEWAY_SESSION <command>
```

## Trap 5: settings path, credentials path

- Settings must live at `plugins.entries.<id>.settings.<key>`. One level up
  (`plugins.entries.<id>.<key>`) is silently ignored and the schema default wins.
- Credentials are **per home** in `<home>/.env`. A profile with correct settings but no key in
  its own `.env` will fail every provider call. Always check the credential in each home.
- `hermes -p <profile> config get|set` is the per-profile interface. `hermes config get` alone
  always reads the default home.

## Trap 6: doctor ignores Nerve profile sidecars

Nerve >= 0.3 reads `<home>/nerve/profile.json` (lean/marie_kondo/...). `plugins doctor` loads a
scratch copy without the sidecar, so it always reports Legacy `16 tool(s)`. The real count is
only in a live session's load line: `Nerve 0.3.1 loaded; profile=lean tools=6`. Set profiles with
`cd <home>/plugins/nerve && HERMES_HOME=<home> ~/.hermes/hermes-agent/venv/bin/python -m hermes_nerve setup --profile <name>`.
Lean/Marie Kondo turn off `context_governor`, so the `jev` context engine is never registered.
Set `context.engine: compressor` there, or Hermes logs "not found" and falls back anyway.

### The profile decides registration; settings only tune (and can only switch OFF)

For a NAMED profile the resolver takes its module set **verbatim** from the plugin's own table
(`modules = dict(PROFILES[name])`). Settings are then applied on top, and the only pass that reads them
can disable a module, never enable one. So a setting written for a module the profile does not register
is configured on paper and off in the run — with nothing visibly broken, which is the worst possible
failure mode for a decision layer:

| setting | module it needs | who registers it |
|---|---|---|
| `gate_mode` != `off` | `action_gate` | `operator` (not `lean`, not `marie_kondo`) |
| `context_engine_mode` / `context_curation_mode` != `shadow`/`off` | `context_governor` | `operator` only |
| `work_supervision_mode` != `shadow` | `work_supervision` | `lean`, `marie_kondo` (not `operator`) |
| `nervous_enabled: true` | `nervous` | every profile except `custom`/`legacy` |

Nerve 0.3.1 sets at a glance: `operator` = reflex, nervous, action_gate, context_governor, receipts,
local_learning; `lean` = reflex, nervous, work_supervision, token_trajectory, receipts; `marie_kondo` =
reflex, work_supervision, token_trajectory, receipts.

Rules that follow, for any home or container you configure:

- **Pick the profile for the modules you want, then write only settings those modules own.** Writing
  `context_*_mode: apply` under `lean` (no `context_governor`) or `work_supervision_mode: advisory` under
  `operator` (no `work_supervision`) buys nothing and hides itself.
- **Write the profile in BOTH places**: the sidecar `<home>/nerve/profile.json` *and*
  `plugins.entries.<id>.settings.nerve_profile`, so a reader of the config sees what the run does.
- **Assert parity at build/setup time**, not by eye: for every setting you write, look up the module it
  needs and fail when the chosen profile does not enable it, printing the resolved module set on success.
  Do the lookup against the plugin's OWN `PROFILES` (import it), never a copy you maintain yourself.
- A profile change is not a settings change: after switching profiles, re-read the resolved module list
  and re-check every setting you carry, or the previous profile's tuning silently stops applying.

## Procedure

1. Enumerate homes: `hermes profile list` + `ls ~/.hermes/profiles/`.
2. Read the plugin's `plugin.yaml` for the real `name:` and required config keys.
3. Per home, compare: directory name, metadata key, enabled list, settings values, git revision.
4. Doctor each home (stripped env) and require registration counts to match.
5. Run one live PTY probe on a home that has never exercised the plugin.
6. Back up before any rename/rewrite, and rewrite metadata by copying the *default home's*
   entry verbatim so provenance is identical everywhere.

Run `scripts/audit_plugin.sh <plugin-id>` for a one-shot table over every home.

## Live probe (the only real activation proof)

`hermes chat -q` / `-z` do **not** register plugin tools and write no plugin log lines — they
prove nothing. Use a PTY:

```bash
tmux new-session -d -s probe -x 200 -y 50 \
  "env -u HERMES_KANBAN_TASK -u HERMES_KANBAN_TASK_ID -u HERMES_KANBAN_BOARD \
   -u HERMES_CRON_SESSION -u HERMES_GATEWAY_SESSION hermes -p <profile>"
sleep 30
tmux send-keys -t probe 'Reply with exactly: OK' Enter
sleep 5
tmux send-keys -t probe Enter          # submit (first Enter often only commits the text)
sleep 45
tmux capture-pane -t probe -p | tail -12
tmux send-keys -t probe '/exit' Enter; tmux kill-session -t probe
```

Then confirm all three in the home:

- `logs/agent.log`: `Nerve ... loaded from <profile>/plugins/nerve; tools=16 headless_worker=False`
- the plugin's own ledger (`<home>/nerve/nervous-events.jsonl` for Nerve): a fresh
  `turn_admission` record carrying a real `request_id` and `latency_ms`
- `<home>/nerve/decision-outcomes.jsonl` for exercised decision paths

A real provider round-trip (`request_id=req_...`, `latency_ms` in the hundreds) is the proof the
engine is wired; a `turn_complete` with `provider_calls=1` on a trivial turn confirms the
cost-saving design (admission only, no follow-up call).

## Reporting

Lead with the per-home PASS/FAIL table. Distinguish three states explicitly — they are not the
same as "broken":

- **configured & verified** (settings + doctor + live load prove it)
- **configured but never exercised** (no ledger history — usage gap, not a defect)
- **misconfigured** (dir/metadata/settings mismatch — actually needs fixing)

State the backup path. Do not claim activation from `plugins list` alone.
