## ADDED Requirements

### Requirement: Hub listing retries a timed-out read over IPv4
A Hub API GET MUST be retried when the read times out, and each attempt MUST
use a new request opened over IPv4 when the host has an A record. A transport
failure MUST NOT be cached as an empty file tree. An HTTP error for a missing
repo MUST still yield no files.

#### Scenario: a timed-out GET is retried
- **Given** the first Hub GET raises `TimeoutError` and the next returns a JSON list
- **When** the listing is fetched
- **Then** the returned value is that JSON list
- **And** each attempt was a distinct request
- **Test:** `tests/test_trend_pick.py::test_hub_json_retries_a_timed_out_read`

#### Scenario: the connection tries IPv4 first
- **Given** a Hub host
- **When** addresses for the connection are resolved
- **Then** the lookup asks for IPv4 (`AF_INET`)
- **Test:** `tests/test_trend_pick.py::test_hub_addresses_are_ipv4`

#### Scenario: a transport failure is not remembered as an empty tree
- **Given** a tree listing that times out, then a later listing that returns files
- **When** the tree is read twice
- **Then** the first read is empty and the second read is the file list
- **Test:** `tests/test_trend_pick.py::test_tree_does_not_cache_a_transport_failure`
