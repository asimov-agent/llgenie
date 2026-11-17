# Fleet memory gate: render / check / status (issue #2058)

## What was verified against the spec

- **`scripts/memory_bootstrap.py` gained `render`, `check`, `status`** (`make memory-render`,
  `make memory-check`, `make memory-status`; `memory-verify` untouched). `render` materializes
  each derived profile's `<profile>/hindsight/config.json` from the ONE shared template and
  creates a missing profile `.env` as EMPTY 0600 — it never writes or prints a key
  (`test_second_render_changes_nothing`, `test_render_never_invents_a_key`).
- **`check` is a daemon/profile consistency gate** with the issue's exit contract: 0 wired,
  1 named drift, 2 missing precondition. Per profile it compares the BUILT daemon env
  (the builder's own `_build_embedded_profile_env` output — not a file read) field-by-field
  against the shared `hermes.env` over `FLEET_ENV_KEYS`, which deliberately EXCLUDES
  `HINDSIGHT_LLM_API_KEY`: the key's PRESENCE is asserted, its value never enters any
  comparison a printed diff could leak (`test_check_and_status_never_print_key_values`).
- **A profile cannot rest on another file's key**: `.env` with no non-empty
  `HINDSIGHT_LLM_API_KEY` (including the `not-needed` placeholder) is a named FAIL
  (`test_check_fails_naming_profile_without_key`).
- **Daemon evidence is measured, never assumed**: the gate prints the pid + port it found,
  reads `/proc/<pid>/environ` for model/base-url/provider and the newest
  `Connection verified:` line (url + model), and `/health` alone never passes — a serving
  daemon with no endpoint environ FAILS (`test_health_alone_never_passes`,
  `test_check_prints_measured_pid_port_and_connection`).
- **The lane preflight runs the `check` gate** (`scripts/lane_preflight.py`
  `memory_step`): rc=1 fails the preflight (a dispatch must not start on a flipped
  endpoint/model); rc=2 prints a WARN and does not red it (a precondition gap, not a
  regression); `--no-memory-check` skips it. The step calls
  `scripts/memory_bootstrap.py check` DIRECTLY — GNU make collapses every recipe failure to
  exit 2, which would make a real rc=1 drift indistinguishable from the rc=2 unprovisioned
  case. The tests drive `lane_preflight.run` over a scratch HERMES_HOME with the fixture
  plugin installed at `plugins/hindsight/embedded.py` and a stub daemon measured via
  `LLGENIE_MEMORY_DAEMON_PORT`.
- **Subset, not equality (AC6)**: the profile set is derived from the manifest
  (`profiles_from_manifest`), and the drift tests assert `expected <= actual` — a NEW wired
  profile never reddens the gate (`test_profile_set_is_subset_so_adding_a_profile_does_not_red`).
- **The gate never reads a live LLM**; it reads config/env files, `/proc`, one local
  `/health` probe and a log tail (AC10).

## Key decisions

- `memory-check` was a no-op alias of `memory-verify` (only `make -n` and agent-wiki cited
  it); it is REPURPOSED as the `check` gate. `memory-verify` stays as it was, so the
  #2068 verify tests are untouched.
- `render` skips a file whose bytes already match the render (mtime preserved) so
  idempotency is byte-for-byte provable, and `DRY_RUN=1` / `--dry-run` reports without
  writing.
- The gate commands derive profiles from `agents/manifest.json` and share HERMES_HOME
  layout facts with `cmd_install`'s `_fleet_dirs` — same seams #2068 left.
- Per AC8 the vehicle touches scripts/, mk/agents.mk + Makefile, tests/, and the
  preflight only — no docs/BOTS.md section (that ownership stays with #2057/#2063).
- Daemon pid/port discovery has a pure-`/proc` FALLBACK (`_proc_listen_pids`): the first
  full `make test-unit` failed 14 gate tests with "no daemon listening" because the
  hermetic test container ships no `ss`/`lsof` — host runs were green, the CI seam was
  not. `/proc/net/tcp{,6}` LISTEN inodes for the port + a `/proc/<pid>/fd` readlink scan
  now answer identically in both worlds (`ss`/`lsof` stay the fast first path);
  `test_listen_pids_falls_back_to_proc_when_ss_and_lsof_are_missing` pins it.
- Stub fixtures bind their OWN port (port 0 + a sentinel-file handshake) instead of
  probe-then-relaunch: on a busy host `/usr/bin/herdr` once squatted a released probe
  port before the stub bound it, and the gate read the stranger's pid (9 flaky fails).
  `test_check_exit2_no_daemon` et al. use `_unbound_port()`, a re-picking probe.

## Current status

- New tests: `tests/test_fleet_memory_gate.py` (hermetic scratch HERMES_HOME + the
  `tests/fixtures/fake-hindsight-plugin/embedded.py` builder + a REAL socket-serving
  `hindsight_stub` daemon so the pid//proc path is measured, not faked).
- Wiring tests updated in place: `tests/test_memory_bootstrap.py` (target recipes now
  name `check`/`render`/`status`), `tests/test_makefile_agents_mk_split.py` (memory-*
  sextet).
