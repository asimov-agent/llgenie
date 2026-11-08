# Fleet memory topology documented (#2057)

## What changed

`docs/BOTS.md` gains a **Fleet memory** section that writes down how the 13 `llgenie-*` profiles'
memory is actually wired — previously it existed only in files outside the repository (a per-profile
`hindsight/config.json`, a per-profile `.env` key, and one shared `~/.hindsight/profiles/hermes.env`)
so it could neither be reviewed nor rebuilt from the tree.

## The topology, measured 2026-11-08 on this host

- Mode `local_embedded`; one embedded daemon per host on `127.0.0.1:9177`
  (`uvx hindsight-api@1.2.0 --idle-timeout 0 --port 9177`, detached from the gateway).
- The plugin keys the daemon off the config `profile` field (`hermes`), **not** `HERMES_HOME`, so two
  sessions on one host share one env file and one daemon.
- Endpoint `openai_compatible` / `deepseek/deepseek-v4-flash-0731` /
  `https://inference-api.nousresearch.com/v1`; embeddings + reranker run locally.
- Key: `HINDSIGHT_LLM_API_KEY` in each profile `.env`; the shared `hermes.env` carries the
  `HINDSIGHT_API_LLM_*` set. Config + env files are `0600`.
- Banks: `bank_id_template: "{profile}"` (per-lane primary) plus `additional_banks: "llgenie-shared"`
  (every lane also writes to and recalls from the shared bank); the legacy `hermes` bank is no longer read.

## The hazard, and why it is written down

The wiring is silently reversible. The log recorded `Connection verified:
openai/deepseek/deepseek-v4-flash-0731` at 02:11:27, then a second session rewrote the shared config
(mtime 02:13:51) and `hermes.env` (mtime 02:14:53) and the same daemon restarted on a local llama.cpp
endpoint — `Connection verified: openai/qwen3.8-27b-iq3_s` at 02:14:29. Because the plugin is keyed to
the config profile name, one session's edit lands on every lane's daemon.

## `/health` is not evidence

`/health` proves only that the HTTP server answers and its DB is connected; it says nothing about the
model or base URL in force. The evidence check is the daemon child PID (`pgrep -af hindsight-api`)
plus `/proc/<pid>/environ` (`HINDSIGHT_API_LLM_MODEL`/`_BASE_URL`/`_PROVIDER`) plus the newest
`Connection verified:` log line.

## Files

- `docs/BOTS.md` (new Fleet memory section before "How the bots stay out of each other's way", plus a
  cross-link from the existing profiles section under `agents/` — issue #791 — to it).
- `docs/changes.d/2026-11-08-fleet-memory-topology-2057.md` (change row).

Docs only — no script, no Makefile target, no code (AC7).

## Not covered

- The profiles reference the lanes preload links to the new section — the Technical names that reference
  as `agents/*/skills/*/references/agent-profiles.md`, an `agents/` change AC7 forbids on this vehicle
  ("touches `docs/` (and its change note) only"). The link is provided from `docs/BOTS.md`'s own profiles
  section instead; wiring the `agents/` skill reference is tracked as #2064.

