# Fleet-memory gate (delta)

## ADDED Requirements

### Requirement: render materialises every profile from the one template, idempotently

`scripts/memory_bootstrap.py render` (reached by `make memory-render`) SHALL write each profile's
`hindsight/config.json` from the single code template and pin the profile `.env` mode to 0600, and
it SHALL be idempotent: running `render` a second time with nothing changed reports zero updated and
changes nothing.

#### Scenario: a second render changes nothing
- **Test:** `tests/test_fleet_memory_gate.py::test_second_render_changes_nothing`
Given a fixture Hermes home with profiles wired by a first render,
When  `render` runs again against the same home,
Then  it exits 0 and reports `0 updated` (and every config file keeps the same bytes and mode 0600).

### Requirement: check gates the shared fleet-memory wiring

`scripts/memory_bootstrap.py check` (reached by `make memory-check`) SHALL exit 0 only when every
configured profile's plugin-built daemon environment matches the shared
`~/.hindsight/profiles/hermes.env` and the profile `.env` carries a non-empty
`HINDSIGHT_LLM_API_KEY`, and the daemon evidence — owning pid on the daemon port, real
`/proc/<pid>/environ`, and the latest `Connection verified` line in the shared log — matches the
documented template (the port the vehicle pins, the model/provider/base-url the docs name). It SHALL
exit 1 naming each offending profile or the daemon on any mismatch, and SHALL exit 2 when a
precondition is absent (no manifest profiles, no shared `hermes.env`, no plugin builder). A daemon
that answers `/health` but whose environ lacks the template's daemon values SHALL never pass.

#### Scenario: a flipped profile endpoint reddens the gate naming the profile
- **Test:** `tests/test_fleet_memory_gate.py::test_check_fails_naming_profile_when_built_env_differs`
Given a fixture home whose shared `hermes.env` was materialised by the plugin builder and one
profile's shared-endpoint value is then flipped,
When  `check` runs,
Then  it exits 1 and names that profile, and it never prints a credential value.

#### Scenario: a healthy daemon without the template's environ never passes
- **Test:** `tests/test_fleet_memory_gate.py::test_health_alone_never_passes`
Given a real local listener stub that answers `/health` on the checked port but whose process
environ carries no `HINDSIGHT_API_*` values,
When  `check` runs against it,
Then  it exits 1 naming the daemon, proving `/health` alone is not accepted.

#### Scenario: daemon evidence answers identically in a tool-stripped seam
- **Test:** `tests/test_fleet_memory_gate.py::test_listen_pids_falls_back_to_proc_when_ss_and_lsof_are_missing`
Given a listening daemon whose pid is discoverable only from `/proc` (no `ss`, no `lsof` — the
shape of the hermetic `make test-unit` container),
When  the gate measures the daemon,
Then  it reports the same owning pid through the `/proc/net/tcp{,6}` LISTEN inodes plus a
`/proc/<pid>/fd` readlink scan — the check never measures differently in CI than on the host.

#### Scenario: missing preconditions exit 2, not 1
- **Test:** `tests/test_fleet_memory_gate.py::test_check_exit2_no_shared_env`
Given a fixture home with no shared `hermes.env` (or no plugin builder),
When  `check` runs,
Then  it exits 2 naming the missing precondition — a distinct verdict from a mismatch.

#### Scenario: fully wired fixtures pass
- **Test:** `tests/test_fleet_memory_gate.py::test_check_passes_over_wired_fixture`
Given a fixture home where every profile's built env equals the shared env, each `.env` carries a
key, and the daemon stub runs with the template's `HINDSIGHT_API_*` environ plus a matching
`Connection verified` log line,
When  `check` runs,
Then  it exits 0 and prints the measured pid, port, model and base url.

### Requirement: lane preflight runs the fleet-memory gate with WARN semantics

`make lane-preflight` SHALL run the fleet-memory `check` gate after the FAST gates — invoking
`scripts/memory_bootstrap.py check` directly rather than through `make memory-check`, because GNU
make collapses EVERY recipe failure to exit 2 and would erase the rc=1/rc=2 distinction the step
maps. A `rc=1` adds `memory-check` to the failed list and reddens the verdict; a `rc=2` prints a
WARN line naming the missing precondition and does NOT red the verdict (an unwired host is a
precondition gap, not a regression).

#### Scenario: a flipped wiring reddens preflight
- **Test:** `tests/test_fleet_memory_gate.py::test_preflight_fails_when_a_profile_drifts`
Given `HERMES_HOME` pointed at a fixture home whose wiring is flipped,
When  `lane_preflight.py run` executes with an empty FAST-gate list,
Then  it exits 1 naming `memory-check`.

#### Scenario: an unwired host only warns
- **Test:** `tests/test_fleet_memory_gate.py::test_preflight_warns_but_stays_green_when_host_unprovisioned`
Given `HERMES_HOME` pointed at a fixture home with no fleet memory provisioned,
When  `lane_preflight.py run` executes with an empty FAST-gate list,
Then  it exits 0 and prints a `memory-check: WARN` line.

### Requirement: the profile-set drift test is a subset assertion

The gate's profile set comes from the fleet manifest, and its tests SHALL assert subset semantics
(expected ⊆ actual): adding a wired profile to the manifest keeps the gate green; the drift test
never hard-reddens merely because the fleet grew a profile.

#### Scenario: a new wired profile keeps the gate green
- **Test:** `tests/test_fleet_memory_gate.py::test_profile_set_is_subset_so_adding_a_profile_does_not_red`
Given a fixture manifest with the expected profiles plus one extra wired profile,
When  `check` runs,
Then  it exits 0 and reports the larger profile count.
