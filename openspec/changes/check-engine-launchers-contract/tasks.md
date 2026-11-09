# check-engine-launchers contract — tasks

- [x] `scripts/check_engine_launchers.py::required_for(arch)` names the CORE launcher set `make install` always writes, intersected with the rows that have an image for `arch`
- [x] `scripts/check_engine_launchers.py::_host_opted_in(bindir, arch)` returns True when the host holds at least one CORE launcher (CI / a fresh machine has none → not opted in)
- [x] `check()` buckets each missing launcher REQUIRED (CORE + opted-in host) vs informational; informational never reds; REQUIRED reds and prints `make engine-launchers ENGINES=<engine>` as the fix
- [x] a host with ZERO launchers (CI) exits 0 with every missing row informational and `N missing (arch X)` in the summary
- [x] tests: `tests/test_check_engine_launchers.py::test_missing_launchers_on_an_uninstalled_host_are_all_informational` — 7 missing on a bare host → exit 0, no REQUIRED
- [x] tests: `tests/test_check_engine_launchers.py::test_a_host_missing_a_required_launcher_fails` — opted-in host missing a CORE pair-mate → exit 1, names it + the make fix
- [x] tests: `tests/test_check_engine_launchers.py::test_a_missing_on_demand_launcher_stays_informational_even_when_opted_in` — on-demand missing on an opted-in host stays informational
- [x] `docs/ENGINES.md` states the REQUIRED/informational split (contract lives here + the script header)
- [x] change-note trio: `agent-wiki/2026-11-08-check-engine-launchers-contract-2296.md`, `docs/changes.d/2026-11-08-check-engine-launchers-contract-2296.md`, `CHANGES.md` regenerated via `make changes-index`
- [x] full `tests/test_check_engine_launchers.py` green (15 passed incl 3 new + 1 premise fix)
