# Install, bootstrap and verify the fleet's Hindsight memory wiring (#2068)

## What changed

The Hindsight memory wiring was only hand-edited host state (per-profile
`hindsight/config.json`, a per-profile `.env` key, one shared `~/.hindsight/profiles/hermes.env`,
one embedded daemon on `127.0.0.1:9177`) with nothing in the tree to install, bootstrap or
verify it. Measured 2026-11-08: 11 of 13 profiles carried an empty `memory.provider`, so the
plugin was installed and listed under `plugins.enabled` but never ran; `/health` stayed green.

This vehicle (scripts/, Makefile, test tree, preflight wiring only — no docs/ section, which
is #2057/#2063) adds `scripts/memory_bootstrap.py` with three entrypoints and a gate:

- **install** — provisions the embedded daemon: `uvx hindsight-api@1.2.0 --idle-timeout 0
  --port 9177`, detached from the gateway, idempotent (a port already served = "no change").
- **bootstrap** — writes each `llgenie-*` profile's `hindsight/config.json`, its
  `HINDSIGHT_LLM_API_KEY` env key and the memory-provider setting from one template, reusing
  the Hindsight plugin's own env builder (`plugins/hindsight/embedded.py`) so bootstrap and
  runtime agree by construction. Idempotent: a second run reports `0 updated, N unchanged`.
  `--dry-run` prints the plan (paths, modes, provider delta) and writes nothing. It never
  invents a key and never prints/copies a credential value.
- **verify** — per-profile PASS/FAIL with daemon pid + port, the live
  `/proc/<pid>/environ` model/base-url (the evidence docs/BOTS.md names), and the newest
  `Connection verified:` log line. A profile whose provider is empty or whose env key is
  absent FAILS with its name — never a silent skip.
- **memory-check** — the gate that reds the board on a failed profile (feeds #2058's drift
  check; this vehicle calls it, it does not redefine it).

## Verified

- `make test-unit` green (incl. the new `tests/test_memory_bootstrap.py`): install idempotent
  (a real listening socket as the external-system stand-in), bootstrap idempotent (`expected
  <= actual`), `--dry-run` byte-identical tree, zero credential hits in output, bootstrap env
  equals the plugin runtime builder, 0600 modes, verify names failing profiles.
- Config + env files are written `0600`.
- `scripts/memory_bootstrap.py` uses the ONE subprocess seam (`scripts/proc.py`) for the PID probe
  and carries a `# proc-allow:` reason only on the detached daemon spawn (`Popen` has no policy in
  `proc.py` and would block a `run_*` call), so `make check-proc-gate` is green.
- The plugin fixture `tests/fixtures/fake-hindsight-plugin/embedded.py` is a stand-in for the
  third-party dependency (the `fake-nerve-plugin` convention, #611), never a mock of the product.
- The PR that carries this change is #2092 (opened from branch
  `agent/issue-2068-feat-memory-install-hindsight-and-bootst`).

## Files

- `scripts/memory_bootstrap.py`
- `tests/test_memory_bootstrap.py`, `tests/fixtures/fake-hindsight-plugin/embedded.py`
- `Makefile` (`memory-install`, `memory-bootstrap`, `memory-verify`, `memory-check`, all
  `.PHONY`; internal automation targets — no `##` help line, because AC9 forbids a docs/
  section (the BOTS.md topology is #2057/#2063) and the fleet-memory commands therefore do
  not enter the README surface)
- this note + `docs/changes.d/2026-11-08-fleet-memory-bootstrap-2068.md` + CHANGES.md row

## Not covered

- The `docs/BOTS.md` topology section is #2057/#2063 (already merged); this vehicle implements.
- The drift gate comparing rendered profiles to the shared env is #2058; `memory-check` calls
  into it, it does not redefine it.
