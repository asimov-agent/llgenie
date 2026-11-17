# Fleet-memory gate: render / check / status for the shared Hindsight wiring

## Why

Issue #2058: the fleet memory topology is documented in `docs/BOTS.md` (issue #2057), and the
bootstrap vehicle exists (`make memory-bootstrap`, `make memory-check` → today an alias of
`verify`), but there is NO gate that answers "is the shared memory wiring actually consistent on
this host right now?". A lane can start against a daemon whose endpoint silently drifted, a profile
whose built daemon env no longer matches the shared `~/.hindsight/profiles/hermes.env`, or a profile
.env with no API key — and nothing in the pre-push flow catches it. `verify` checks per-profile key
presence and provider wiring only; it never compares the built env against the shared env, never
reads the daemon's real `/proc/<pid>/environ`, and never compares endpoint/model against the one
documented template.

## What Changes

- ADDED: `scripts/memory_bootstrap.py` grows three subcommands — `render` (writes every profile's
  `hindsight/config.json` and pins the `.env` from the one template, idempotent: a second render
  changes nothing), `check` (the gate), and `status` (pure report, exits 0).
- ADDED: `check` semantics — exits 0 when every configured profile's plugin-built daemon env matches
  the shared `hermes.env` and carries a non-empty `HINDSIGHT_LLM_API_KEY`, and the daemon's real
  `/proc/<pid>/environ` plus the latest `Connection verified` log line match the documented template
  (model/provider/base-url, pinned version 1.2.0, port 9177); exits 1 naming the profile(s) or the
  daemon on any mismatch; exits 2 when a precondition is absent (no manifest profiles, no shared
  `hermes.env`, no plugin builder). `/health` alone never passes: the daemon evidence is pid + port
  + environ + connection line.
- ADDED: make targets `memory-render` and `memory-status`; `memory-check` stops being a `verify`
  alias and runs the new `check` subcommand.
- ADDED: `make lane-preflight` runs `memory-check` after the FAST gates as a host-only step: rc=1
  reddens the preflight verdict, rc=2 prints a WARN line (fleet unwired on this host) without
  redning — a host that has never provisioned memory is a precondition gap, not a regression.
- ADDED: hermetic tests (`tests/test_fleet_memory_gate.py`) over the existing
  `tests/fixtures/fake-hindsight-plugin/embedded.py` seam plus a real local daemon stub: render
  idempotency, flipped-endpoint FAIL, missing-key FAIL, healthy-`/health`-but-no-daemon-env FAIL,
  rc=2 precondition path, preflight WARN/FAIL wiring, and subset (expected ⊆ actual) profile-set
  drift semantics.

## Impact

- Affected specs: `hindsight-memory-bootstrap` (ADDED requirements: fleet-memory gate).
- Affected code: `scripts/memory_bootstrap.py`, `scripts/lane_preflight.py`, `mk/agents.mk`,
  `tests/test_fleet_memory_gate.py`, plus the changelog triad (agent-wiki note, changes.d fragment,
  CHANGES.md row).
- Vehicle discipline (issue AC8): scripts/, Makefile and tests only — no `docs/BOTS.md` topology
  section change (the docs sibling issues own it), no new CI job, no `FAST_GATES` edit.
