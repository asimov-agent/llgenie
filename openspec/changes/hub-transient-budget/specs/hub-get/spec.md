# hub-get

## ADDED Requirements

### Requirement: the shared Hub GET retries the whole transient set on a stated budget

`scripts/hf_auth.py::hub_open` MUST retry the transient set — 429, 500, 502, 503, 504, transport
failures and timeouts — and MUST raise on the first answer for any other status. A 429 MUST wait the
Hub's own window (`rate_limit_wait`) at most `RATE_LIMIT_WAITS` times; every other transient outcome
MUST retry on a doubling ladder bounded by `HUB_MAX_ATTEMPTS`. The transport MUST be pluggable so a
caller keeps its own (IPv4) transport without carrying its own budget.

#### Scenario: a 5xx then an answer

- **Given** a Hub that answers 503 twice and then 200 with the file list
- **When** the shared seam opens that URL
- **Then** it SHALL return the answer, after exactly three requests
- **Test:** `tests/test_hub_transient_budget.py::test_hub_open_retries_a_503_then_reads_the_answer`

#### Scenario: a sustained 5xx is bounded and loud

- **Given** a Hub that answers 503 forever and a three-try budget
- **When** the shared seam opens that URL
- **Then** it SHALL raise the 503 after exactly the budget's requests
- **Test:** `tests/test_hub_transient_budget.py::test_an_eternal_503_fails_loudly_on_the_bounded_budget`

#### Scenario: a definitive status is not retried

- **Given** a Hub that answers 404
- **When** the shared seam opens that URL
- **Then** it SHALL raise after exactly one request
- **Test:** `tests/test_hub_transient_budget.py::test_a_definitive_status_is_not_retried`

#### Scenario: the rate limit waits its window, twice at most

- **Given** a Hub that answers 429 forever carrying `t=1`, and the waits recorded
- **When** the shared seam opens that URL
- **Then** it SHALL wait the window twice and raise on the third answer
- **Test:** `tests/test_hub_transient_budget.py::test_an_eternal_429_stops_after_the_stated_window_waits`

### Requirement: the pick uses that seam and never caches a transient answer as a fact

`scripts/model_engine_pick.py` MUST open Hub API URLs through `hf_auth.hub_open` (its own IPv4
transport passed as `opener`) and MUST NOT carry a second retry ladder. `_tree` MUST treat a
transient status as unknown **without caching** an empty tree, so a later call asks the Hub again.

#### Scenario: a 503 is retried into a real tree

- **Given** the pick's Hub base pointed at a Hub that answers 503 once and then lists one file
- **When** the pick resolves that repo's tree
- **Then** it SHALL return that file, having asked twice
- **Test:** `tests/test_hub_transient_budget.py::test_the_pick_tree_retries_a_503_instead_of_reporting_an_empty_repo`

#### Scenario: an exhausted throttle is not cached as an empty repo

- **Given** a Hub that answers 429 forever and an empty pick tree cache
- **When** the tree is resolved twice
- **Then** both answers SHALL be empty
- **And** the second call SHALL have reached the Hub (no cached empty tree)
- **Test:** `tests/test_hub_transient_budget.py::test_the_pick_tree_does_not_cache_a_transient_failure`
