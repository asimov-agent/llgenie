# Tasks — fleet-memory-gate-2058

## 1. Implement (maps to issue ACs)

- [x] `scripts/memory_bootstrap.py`: add `render` subcommand — template-write every profile's
      `hindsight/config.json` (0600), ensure the profile `.env` exists pinned to 0600, never invent
      a key value; report `N updated, M unchanged` (AC1)
- [x] `scripts/memory_bootstrap.py`: add `check` subcommand — per profile: built daemon env (via the
      plugin builder seam) == shared `~/.hindsight/profiles/hermes.env` map over the documented env
      keys (API key excluded from this comparison), and a non-empty `HINDSIGHT_LLM_API_KEY` in the
      profile `.env`; daemon: port-owning pid whose name carries `hindsight`, real
      `/proc/<pid>/environ` matching the template model/provider/base-url, and the last
      `Connection verified:` line in the shared log matching the same values; exit 0 ok / 1 mismatch
      naming the profile or daemon / 2 precondition missing (AC2, AC3, AC4)
- [x] `scripts/memory_bootstrap.py`: add `status` subcommand — pure report (daemon pid/port/environ +
      connection line, per-profile key/config presence, shared env path); exit 0 (issue step 1)
- [x] `mk/agents.mk`: `memory-render` and `memory-status` targets; `memory-check` now runs `check`
      (no longer a `verify` alias); `PORT=` passthrough; all new/changed targets declared `.PHONY`
      (AC7)
- [x] `scripts/lane_preflight.py`: run the `check` gate DIRECTLY after the FAST gates (`make`
      collapses recipe failures to exit 2) — rc=1 reddens the
      verdict naming `memory-check`; rc=2 prints a WARN line without redning (AC5)
- [x] `tests/test_fleet_memory_gate.py`: hermetic tests over the fake-plugin fixture seam + a real
      local listener stub — render idempotency, flipped endpoint FAIL, missing key FAIL,
      healthy-but-no-daemon-env FAIL, precondition rc=2, wired-fixture rc=0, preflight WARN/FAIL
      wiring, subset (expected ⊆ actual) profile-set drift, and the tool-stripped `/proc`
      fallback for daemon pid discovery (the hermetic container has no `ss`/`lsof`)
      (AC1, AC2, AC3, AC4, AC5, AC6)

## 2. Verify

- [x] `make test-unit` green at the final head; targeted tests green before/after sabotage
      (proven: 3991 passed, 0 failed; targeted 73/73 green)
- [x] live-host proofs: the direct `scripts/memory_bootstrap.py check` seam over the wired fixture
      (live listener stub pid measured) rc=0; flipped endpoint+model rc=1 naming `llgenie-alpha`;
      `make memory-check` over the same flip exits 2 — the make recipe-failure collapse that forces
      the preflight to call the gate directly
- [x] `make openspec-validate NAME=fleet-memory-gate-2058` exits 0
- [x] `make check-wiring`, `make lint`, `make check-docs`, `make issue-bot-gates` green
      (proven: check-wiring rc=0, lint rc=0, check-docs rc=0; issue-bot-gates re-run green at the final head)

## 3. Docs triad

- [x] Docs triad: `agent-wiki/2026-11-17-fleet-memory-gate-2058.md` + `docs/changes.d/` fragment +
      CHANGES.md row (`make changes-index`, `make check-docs` green)

## 4. Ship verification

- [x] Ship verification: the final head carries the ticked AC mirrors + `closes #2058`, and
      `make lane-preflight` prints a `memory-check:` line with its verdict at the final head
