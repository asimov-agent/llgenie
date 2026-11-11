---
name: hermes-memory-config
description: Use when wiring a Hermes memory provider's model and key.
version: 1.0.0
author: llgenie-planner
license: MIT
metadata:
  hermes:
    tags: [hermes, memory, hindsight, configuration, daemon]
    related_skills: [hermes-agent]
---

# Hermes memory provider configuration

The class of work: "is my memory provider running, and is it wired to the right model/key?" — change the
config, restart the backing daemon, and prove the round trip with real tool output instead of asserting it.

## When to Use

Trigger on: "is hindsight/retaindb/memory running", "is it connected to the local LLM server", "point memory
at provider X with key Y", "switch memory between local llama.cpp and a hosted endpoint", or any edit of
`$HERMES_HOME/hindsight/config.json` / `~/.hindsight/profiles/*.env`. Also before answering any question about
which model the memory backend uses — the answer comes from the daemon's process env and log, not from config.

## Always-on rules

- **The effective config is the running daemon's, not the file's.** Read `/proc/<pid>/environ` for the
daemon and its log's `Connection verified: <provider>/<model>` line before answering. The config file, the
materialized `.env`, a stored memory, and what a previous session believed can all disagree; only the process
and its log are evidence. State the pid/sha you measured against.
- **Never put an LLM API key in the plugin's `config.json`.** Leave the key to the profile `.env` secret so
it lives in exactly one place; the plugin resolves it for you (see resolution order below).
- **Verify with a write path, not just a health check.** `/health` proves the store is up; only a
retain → recall round trip proves the extraction LLM is reachable with the configured key.
- **A config edit does not reach a plugin instance that already initialized.** The live agent caches config
at `initialize()`; the on-disk edit plus its drift check can make the *stale* instance rewrite your change
back. Verify after the next real tool call, not after the `write_file`.
- **Never `pkill -f '<name>'`.** The pattern matches the `bash -c` command line of the call doing the
killing, so the shell dies with the target (exit -15, half the cleanup undone). Use a bracketed pattern to
list (`pgrep -af 'uvx [h]indsight'`) and kill by PID.
- **"All N profiles" is a measurement, not an inference.** When the claim is that every profile or lane is
  wired, run the check per profile and report the count you measured (`thirteen profiles: ...`). A sample plus
  "the rest are identical" is exactly what gets challenged — and if some lanes have not taken a turn yet say
  so plainly (configured for 13, exercised on 5), naming the ones with no bank yet.
- **Say "fixture" in the same breath as a deliberately broken test result.** A negative test prints the
  broken values (the old endpoint, the missing key); the user reads that as a regression in their live setup.
  Run fixtures under their own scratch root and label the output `fixture:` on the line, or the next message
  is spent reassuring instead of finishing.
- **One daemon per profile name.** The embedded daemon keys off a profile name (default `hermes`); two
Hermes profiles that never set `profile` share one `.env` and one daemon, and each start rewrites the other's
model. Give each lane its own `profile` value, or expect them to fight.

## Procedure (hindsight, local embedded + hosted LLM)

1. **Locate the config.** `$HERMES_HOME/hindsight/config.json` (profile-scoped) is read first, then
   `~/.hindsight/config.json` (legacy shared). Keys that matter: `mode`, `llm_provider`, `llm_base_url`,
   `llm_model`, `profile`, `bank_id`.
2. **Pick the mode.** `local_embedded` = managed `hindsight-api` daemon on this machine (embeddings and
   reranker stay local). `local_external` = attach to an existing instance. `cloud` = API key only.
3. **Map the LLM provider.** There is no `nous` value: a Nous/OpenAI-wire endpoint is
   `llm_provider: "openai_compatible"` plus `llm_base_url` and `llm_model`. The plugin maps
   `openai_compatible` → daemon provider `openai`, so a local llama.cpp server and a hosted endpoint are the
   same shape and differ only in base URL, model alias and key.
4. **Leave the key out of the config.** Resolution order: `config.llm_api_key` → secret
   `HINDSIGHT_API_LLM_API_KEY` / `HINDSIGHT_LLM_API_KEY` (profile `.env`) → the key already on disk in
   `~/.hindsight/profiles/<profile>.env`. Confirm the `.env` key equals the provider key by hash before
   trusting it — the same variable name may hold a leftover local-server key.
5. **Materialize the env file and restart through the plugin's own code**, not by hand-editing
   `~/.hindsight/profiles/<profile>.env`: it must be `0600`, and a hand-written file drifts from what the
   plugin will rebuild. Run the builder with the Hermes venv interpreter
   (`~/.hermes/hermes-agent/venv/bin/python`) — the tools interpreter lacks `ruamel` and cannot import the
   plugin, and the `hermes-agent` directory itself must be on `sys.path` — an editable install resolves
   `hermes_cli` but not top-level modules like `hermes_yaml`, so a bare import dies with
   `ModuleNotFoundError: hermes_yaml`. See `references/hindsight-embedded.md` for the snippet and the
   functions to call.
   When you need this for **many** profiles, use **one interpreter per profile**: `get_hermes_home()` and the
   plugin's module state are process-global, so a single loop over `HERMES_HOME=...` values silently reads the
   first profile's home for all of them — and every profile then "passes" the same comparison.
6. **Cold-start via an agent tool call** (`hindsight_recall`), so the daemon is spawned detached by the
   process supervisor. Starting it from a throwaway script reports `Daemon exited during initialization
   (exit code 0)`: the child is fine, the parent script exiting takes it down.
7. **Verify all four:** daemon log `Connection verified: openai/<model>` at the boot timestamp ·
   `curl -s 127.0.0.1:9177/health` → `healthy`/`connected` · `GET /v1/default/banks/<bank>/memories/list`
   showing the fact you retained · `hermes memory status` → provider active.

## Sharing one daemon across many profiles

When several Hermes profiles on one machine should share a single Hindsight daemon, DB and bank:

1. **Pin `profile` explicitly to the same value** (`"hermes"`) in every profile's `hindsight/config.json`.
   The embedded daemon is keyed by that config value, not by `HERMES_HOME`; identical values mean one
   `~/.hindsight/profiles/<profile>.env`, one port, one pg0 database, one bank.
2. **Make the built env byte-identical everywhere** — same `mode`, `llm_provider`, `llm_base_url`,
   `llm_model`. One profile pointing at a different endpoint rewrites the shared env file and restarts the
   daemon for everybody; this is exactly how a Nous config gets silently reverted to a local llama.cpp one
   minutes later.
3. **Put the provider key in each profile's own `.env`.** Secret scopes are per profile. A profile with no
   key of its own still works, because the builder falls back to the key already on disk in the shared env —
   which makes it silently dependent on that file. When the *shared env itself* has no key (fresh host, or
   after a key is removed), `openai_compatible` builds the placeholder `not-needed` and materializes it over
   the shared env, so every lane inherits a dead key. Treat the per-profile key as the redundancy requirement
   it is, and check it as a file fact (`grep '^HINDSIGHT_LLM_API_KEY=.' <profile>/.env`) — a bare shell has no
   Hermes secret scope, so the builder alone cannot prove the profile carries one.
4. **Set `memory.provider: 'hindsight'` in each profile's `config.yaml`.** Having the plugin installed and
   listed under `plugins.enabled` is not enough; until the provider is set the plugin never runs.
5. **Verify per profile, not just for the one you edited:** run the builder with each `HERMES_HOME`
   (`_build_embedded_profile_env(_load_config())`) and require it to equal the on-disk `hermes.env` owned
   keys, then `hermes -p <profile> memory status` must say `Provider: hindsight` + `active`.
6. **Bank layout for a fleet on one daemon:** `bank_id_template: "{profile}"` gives each Hermes profile its
   own bank, and `additional_banks: "<shared>"` adds one bank every lane writes to *and* recalls from (repo
   conventions, gate recipes). Resolve the template before trusting it — `{profile}` is already the full
   Hermes profile name, so `"llgenie-{profile}"` yields `llgenie-llgenie-tester`. Keep `bank_id` as the
   static fallback for when the template yields nothing, and mark banks nobody should read as retired by
   leaving them out of `recall_additional_banks` (nothing is deleted; they stay on disk).

## Always-on daemon (surviving reboot and gateway restarts)

The daemon is on-demand by default: the plugin spawns it on the first memory call and `--idle-timeout`
stops it again, so after a reboot nothing is running until a bot takes a turn (~20–30 s cold start).
A `systemd --user` unit makes it permanent without changing the plugin's wiring:

```ini
[Service]
Type=simple
Environment=HOME=%h
EnvironmentFile=%h/.hindsight/profiles/<plugin-profile>.env   # the plugin's own materialized env
Environment=HINDSIGHT_API_DATABASE_URL=pg0://hindsight-embed-<plugin-profile>
Environment=HINDSIGHT_API_DAEMON_LOG=%h/.hindsight/profiles/<plugin-profile>.log
Environment=HINDSIGHT_API_PORT=9177
Environment=HINDSIGHT_API_HOST=127.0.0.1
ExecStart=<uvx-abs-path> hindsight-api@1.2.0 --idle-timeout 0 --port 9177
Restart=always
[Install]
WantedBy=default.target
```

- `--idle-timeout 0` matters: the env file carries `HINDSIGHT_EMBED_DAEMON_IDLE_TIMEOUT=300`, and a service
  that self-stops at five minutes is not a service.
- **`HINDSIGHT_API_HOST` is not optional.** The plugin's own manager pins the daemon to loopback, but a unit
  that omits the variable lets uvicorn bind `0.0.0.0` — and the API has no request auth of its own, so the
  whole memory store is reachable from the LAN. Set it, then prove it: `ss -tlnp | grep :<port>` shows
  `127.0.0.1`, and a connect attempt to the host's LAN address is refused.
- **A unit's output goes to journald, not to the profile log file.** `~/.hindsight/profiles/<p>.log` stops at
  the last plugin-spawned boot; read `journalctl --user -u <unit> -f` for the service, and do not treat the
  frozen file as "the daemon is idle". Any check that greps the log file for `Connection verified:` still
  works (it is the last boot's line) but its timestamp can be older than the running process.
- Take the four `HINDSIGHT_*` values from the **running daemon's** `/proc/<pid>/environ`, not from the env
  file alone — the manager injects the `pg0://` database URL, the daemon log path and the port.
- `loginctl enable-linger <user>`, or the unit only starts when the user logs in.
- The plugin reuses a healthy daemon on the port it expects, so the unit and the on-demand path do not fight.
- Verify like a service: stop daemon **and** its pg0 postgres (the reboot case), start, and require
  `/health` + the bank list to come back; then `systemctl --user kill -s SIGKILL` and watch `NRestarts`
  increment and health return.

## Fleet check and render script (this host)

`$HOME/bin/llgenie-hindsight-setup.sh` is the tested implementation of the whole procedure for a fleet of
profiles: `render` writes every profile's `config.json` + `.env` keys from one template (idempotent — a second
run must print `0 updated, N unchanged`), `check` fails naming the profile when a built env differs from the
shared env, when a profile's `.env` has no non-empty `HINDSIGHT_LLM_API_KEY`, when the live daemon's
endpoint/model differ from the template, or when the daemon binds anything but loopback, and `status` prints
pid/port/endpoint/model/health plus each profile's `memory.provider`. Exit 0 ok / 1 failed / 2 precondition.
Reach for it before hand-editing anything per profile, and read it if you need the builder-import snippet.

## Pitfalls

- **`hermes memory status` only says installed/available.** It does not report which LLM or key the daemon
  is using — never let it stand in for the proc-env + log check.
- **Recall ranking is not a health signal.** Stale memories that contradict the new config ("LLM is llama.cpp
  on 8081") still rank highly for several consolidations after the change; the bank can hold both. Trust the
  log and `/proc`, and retain a corrective fact naming the old endpoint as retired.
- **A leftover second daemon is not the one serving you.** Ports differ per profile; a stale
  `--idle-timeout 0` daemon on another port with another model will look healthy while your profile's daemon
  is down. Match the port the plugin reports to the pid you inspected.
- **Restarting the agent to pick up config kills the session you are in** when the TUI is attached to the
  gateway process. Prefer letting the plugin materialize+restart on the next tool call over restarting the
  gateway from inside a turn.
