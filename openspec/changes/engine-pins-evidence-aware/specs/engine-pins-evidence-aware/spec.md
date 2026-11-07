# engine-pins-evidence-aware

## ADDED Requirements

### Requirement: a red pin-producing cell skips the publish-poll immediately

When the newest completed engine-build dispatch run on the branch has already concluded a red cell
(failure/cancelled/timed_out) for a repinned engine, and `check_engine_pins_published.py check` runs
with a wait (`--wait-min`) and the repo+branch named, it MUST conclude immediately with a recorded
`SKIPPED` decision (engine, run id, red conclusion) — not burn the 290-minute wait on a publish that
can never happen.

WHEN a red pin-producing cell is read before the poll
THEN the check prints `SKIPPED engine=<e>: pin-producing cell(s) concluded <red> (run <id>)` and
returns 0 without starting the poll.

#### Scenario: a red producing cell is read before the poll

- **Given** the producer cell for a repinned engine already concluded `failure` (`42180155067`)
- **When** the check runs with `--wait-min` and repo+branch named
- **Then** it prints `SKIPPED engine=<e>: pin-producing cell(s) concluded failure (run 42180155067)` and returns 0
- **And** it never starts the registry poll
- **Test:** `tests/test_check_engine_pins_published.py::test_red_pin_producing_cell_skips_instead_of_waiting`
  and `::test_non_success_cell_skips_a_success_red_and_no_conclusion_wait` drive a fake producer stream;
  the digest probe would AssertionError if reached.

### Requirement: the pin-published path is unchanged

When the producing cell concluded success and the exact tag resolves a manifest, the check MUST be
green exactly as before — the evidence pre-poll is an early out, never a weaker gate.

WHEN the pin is published
THEN the check passes as before, and a success cell paired with a persistent-404 tag still reds.

#### Scenario: the pin is published

- **Given** the producing cell concluded success and the tag resolves a manifest
- **When** the check runs with a wait
- **Then** it is green exactly as before
- **Test:** `tests/test_check_engine_pins_published.py::test_a_404_is_polled_until_the_producer_publishes`
  (unchanged); a success cell + persistent 404 tag reds (same test file).

### Requirement: the pre-poll is hermetic and off unless CI asks for it

The evidence pre-poll MUST be inert for a plain local check and for a check that does not name the
repo+branch: those are pure registry probes and never read producer cells, so a local run stays
hermetic and fast.

WHEN a check has no `--wait-min`, or has a wait but no repo+branch
THEN it is a pure registry probe and never reads producer cells.

#### Scenario: nothing is repinned

- **Given** no engine differs from the base
- **When** the check runs
- **Then** it is green and hermetic — no producer query, no registry probe
- **Test:** `tests/test_check_engine_pins_published.py::test_no_engine_repinned_is_green_and_hermetic` (unchanged).

#### Scenario: a one-shot local check stays a pure registry probe

- **Given** a check with no `--wait-min` (or with a wait but no repo+branch)
- **When** it runs
- **Then** it is a pure registry probe and never reads producer cells
- **Test:** `tests/test_check_engine_pins_published.py::test_evidence_pre_poll_off_without_wait_or_repo_branch`.
