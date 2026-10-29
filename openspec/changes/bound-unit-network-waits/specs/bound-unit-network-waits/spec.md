# bound-unit-network-waits

## ADDED Requirements

### Requirement: the hf download child carries an explicit ceiling

`scripts/model_engine_pick.py::download` MUST pass an explicit `timeout=` to the
`scripts/hf_download.py` child — one child per planned file — using the module's stated
`DOWNLOAD_TIMEOUT` (default 3600 s, overridable with `LLGENIE_DOWNLOAD_TIMEOUT`).

A child that outlives the ceiling MUST fail LOUDLY: `subprocess.TimeoutExpired` is caught and re-raised
as `SystemExit` whose message names the repo/file, the seconds exceeded and the full command that was
run. It MUST NOT return an empty result, and it MUST NOT let the 6-hour job default be the only bound.

WHEN a planned file's `hf_download.py` child runs longer than `DOWNLOAD_TIMEOUT`
THEN the caller fails with a message naming that command, instead of waiting indefinitely.

#### Scenario: the child is given the module's ceiling

- **Given** a one-file download plan whose Hub tree listing is a fixture
- **When** `download` runs through the `hf_download.py` subprocess path
- **Then** the child was started with `timeout=` equal to `mp.DOWNLOAD_TIMEOUT`, and that value is a
  positive number no larger than an hour
- **Test:** `tests/test_model_engine_pick.py::test_download_bounds_the_hf_child_with_an_explicit_timeout`

#### Scenario: a real child that never returns is killed at the ceiling

- **Given** a real `hf` CLI that sleeps past a 2 s ceiling
- **When** `download` runs that child
- **Then** it raises `SystemExit` inside the ceiling, and the message names `hf_download.py`, the
  planned file, and `exceeded 2s`
- **Test:** `tests/test_model_engine_pick.py::test_a_stalled_hf_child_fails_loudly_naming_the_command_and_the_bound`

### Requirement: one Hub lookup spends at most a small, stated total on 429 waits

`scripts/hf_auth.py::hub_open` MUST bound the time ONE lookup spends sleeping on Hub 429s by a total,
`RATE_LIMIT_TOTAL_BUDGET` (default 60 s, overridable with `HUB_RATE_LIMIT_BUDGET`), in addition to the
existing count ceiling `RATE_LIMIT_WAITS`.

A 429 whose window (`rate_limit_wait`) does not fit what is left of that total MUST raise immediately
instead of sleeping. The raised error MUST be the same 429 — the Hub's status and headers unchanged —
with a message that states the attempts spent, the 429 waits spent, the seconds slept and the budget.

WHEN a Hub lookup meets a 429 whose stated window exceeds the remaining total budget
THEN it raises that 429 at once, and the message reports the attempts and the budget.

#### Scenario: a capped 600 s window is never slept

- **Given** a Hub that answers HTTP 429 with `RateLimit: "api";r=0;t=600` on every request
- **When** `hub_open` opens a Hub URL
- **Then** it raises the 429 without sleeping at all
- **And** the total budget is smaller than one Hub window (`RATE_LIMIT_WAIT_CAP`)
- **Test:** `tests/test_hf_auth.py::test_a_429_window_that_does_not_fit_the_budget_fails_before_sleeping`

#### Scenario: the ceiling is a sum, not a count

- **Given** a Hub that names 40 s on every 429, a count ceiling of 2 windows, and a 60 s total budget
- **When** `hub_open` opens a Hub URL
- **Then** it slept only the one wait that fit (40 s), never two (80 s)
- **And** it raised the 429
- **Test:** `tests/test_hf_auth.py::test_the_429_ceiling_is_a_total_budget_not_a_count_of_waits`

#### Scenario: the failure names the attempts and the budget

- **Given** the same 40 s throttle under a 60 s total budget
- **When** `hub_open` fails on it
- **Then** the raised message states `2 attempt(s)`, `1 429 wait(s)` and `40s of the 60s budget`
- **Test:** `tests/test_hf_auth.py::test_the_429_failure_names_the_attempts_it_spent_and_the_budget`

### Requirement: the existing 429 policy keeps working under the total

The count ceiling (`RATE_LIMIT_WAITS`), the reset on a non-429, and `rate_limit_wait`'s header
/ five-minute-default / ten-minute-cap policy MUST be unchanged: a throttle whose waits fit the total
still waits them and then succeeds.

WHEN the waits named by the Hub fit inside the total budget
THEN `hub_open` sleeps them exactly as before, and a later answer is returned.

#### Scenario: a fitting throttle still waits twice and then fails

- **Given** a Hub that answers 429 forever with `t=1`, a count ceiling of 2 and a real loopback server
- **When** `hub_open` opens that URL
- **Then** it slept `[1, 1]` and stopped after three requests
- **Test:** `tests/test_hub_transient_budget.py::test_an_eternal_429_stops_after_the_stated_window_waits`

#### Scenario: a third consecutive 429 still stops the download GET

- **Given** a Hub GET that is rate-limited every time with `t=1`
- **When** `hub_open` is called
- **Then** the third 429 raises and no fourth attempt is made
- **Test:** `tests/test_hf_download_retry.py::test_hub_open_fails_on_the_third_429`
