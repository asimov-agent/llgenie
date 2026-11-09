# check-engine-launchers-contract

## MODIFIED Requirements

### Requirement: a missing launcher's informational/REQUIRED class matches the sweep's exit code

`scripts/check_engine_launchers.py` must make its exit code agree with the stated contract (issue #2296). A
missing launcher is informational on a host with zero launchers (CI's normal state) and for every on-demand
engine (litert, mlx, ollama, vllm, …), so a host may legitimately have none and the sweep exits 0. Once a
host has installed at least one CORE launcher (`make install` always writes the llama.cpp / llama.cpp-prism
pair), the absent half of that pair is REQUIRED and reds the gate, naming `make engine-launchers
ENGINES=<engine>` as the fix. A stale launcher still reds everywhere, and `CHECK_REGISTRY=1` still fails a
tag no manifest resolves.

#### Scenario: an uninstalled host with no launchers stays green

Given a host (CI, a fresh checkout) whose bin dir holds no launcher,
When `check(bindir, arch)` runs,
Then every missing launcher — CORE and on-demand — is printed informational, the summary reads
`N missing (arch vulkan)`, and the check exits 0.
- **Test:** `tests/test_check_engine_launchers.py::test_missing_launchers_on_an_uninstalled_host_are_all_informational`

#### Scenario: an opted-in host missing a CORE launcher reds

Given a host that has installed at least one CORE launcher (e.g. llama.cpp) but is missing the other half of
the CORE pair (llama.cpp-prism),
When `check(bindir, arch)` runs,
Then the missing CORE launcher is REQUIRED, the check exits non-zero, names the missing engine, and prints
`make engine-launchers ENGINES=<engine>` as the fix.
- **Test:** `tests/test_check_engine_launchers.py::test_a_host_missing_a_required_launcher_fails`

#### Scenario: a missing on-demand launcher stays informational on an opted-in host

Given a host holding the full CORE pair but missing an on-demand engine (litert, mlx, ollama, vllm, …),
When `check(bindir, arch)` runs,
Then the missing on-demand engine is printed informational and does not by itself red the check.
- **Test:** `tests/test_check_engine_launchers.py::test_a_missing_on_demand_launcher_stays_informational_even_when_opted_in`
