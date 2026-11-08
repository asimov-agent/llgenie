# Install Hindsight and bootstrap+verify every llgenie profile's memory wiring

## Why

The Hindsight memory wiring exists only as hand-edited host state: a per-profile
`hindsight/config.json`, a per-profile `.env` key, and one shared
`~/.hindsight/profiles/hermes.env` read by a single embedded daemon on
`127.0.0.1:9177`. Nothing in the tree installs it, and nothing brings a profile —
let alone all 13 `llgenie-*` profiles — to a working state. A new host, a new
profile, or a rebuilt machine requires an operator to rediscover four files and
two credential locations by hand.

Measured 2026-11-08 on the orchestrator host: 11 of 13 profiles carried an empty
`memory.provider`, so the Hindsight plugin was installed and listed under
`plugins.enabled` but never ran; two sessions sharing the plugin's default profile
name rewrote each other's endpoint (`Connection verified:` flipped from one model
to another between 02:11 and 02:14 while `/health` stayed green). Neither failure
is visible to any gate.

## What changes

This vehicle adds the install + bootstrap + verify path, driven by the lanes'
preflight wiring, in `scripts/` and `Makefile` only (no `docs/` change — that is
#2057/PR #2063 already merged; no duplication of #2058's drift-gate logic).

1. An **install** entrypoint provisions the embedded Hindsight daemon on the host:
   pinned version, fixed port `9177`, idle-timeout disabled, detached from the
   gateway, idempotent (a second run changes nothing).
2. A **bootstrap** entrypoint writes each requested profile's `hindsight/config.json`,
   its own `HINDSIGHT_LLM_API_KEY` env key and the memory-provider setting from one
   template; idempotent; never prints or copies a credential value.
3. A **verify** step reports per-profile PASS/FAIL with the daemon pid + port, the
   live `/proc/<pid>/environ` model and base-url, and the newest
   `Connection verified:` line — a profile with an empty provider or absent env key
   FAILS with its name, never a silent skip.
4. A **dry-run** mode prints the full plan (paths, modes, provider delta) and writes
   nothing.
5. The bootstrap reuses the plugin's own env builder rather than re-implementing it,
   so the bootstrap and the runtime agree by construction.
6. The verification result feeds the `make memory-check` gate so a poorly-bootstrapped
   fleet is a red signal, not a silent one.
7. Config and env files are written `0600`.

## Who

ci-pipelines-maintainer (this lane owns the fleet memory wiring; the measured
evidence and the daemon shape come from the orchestrator host documented in #2057).
