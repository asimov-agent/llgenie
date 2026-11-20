## ADDED Requirements

### Requirement: the committed-pin live check waits out the producer push window, bounded
The committed-scope published-pin check SHALL support a patience window: after one
probe sweep of every committed cell, only the UNRESOLVED refs are re-probed at a fixed
retry interval until ONE deadline shared by the whole check — never one window per
cell — and the check SHALL resolve green the moment a manifest appears inside the
window, printing a loud `PATIENCE` line naming each ref it is waiting on.

#### Scenario: a pin whose image lands mid-battery is green
- **WHEN** a committed cell's manifest is absent at the first probe but resolves
  within the window
- **THEN** the check exits 0, its output names the ref it re-probed, and the wait ends
  at the first successful re-probe (not the full window).

#### Scenario: a genuinely unpublished pin still reds at the deadline
- **WHEN** a committed cell's manifest never resolves
- **THEN** the check exits 1 with the `NOT PUBLISHED` line and the `[select]` dispatch
  line for that cell, the re-probe loop having stopped AT the bounded deadline, and the
  total waited time never exceeding the window.

#### Scenario: the window is opt-in per caller
- **WHEN** no patience value is passed and `ENGINE_PINS_PATIENCE_SECONDS` is unset
  (every PR lane, every local `make check-engine-pins-published` run)
- **THEN** each cell is probed exactly once and an unresolved ref reds immediately —
  pin-bump strictness (a PR may not merge while its image is unpublished) is unchanged.

#### Scenario: a malformed knob is loud and defaults to impatient
- **WHEN** `ENGINE_PINS_PATIENCE_SECONDS` is set to a non-numeric value
- **THEN** the check prints a WARN naming the bad value to stderr and behaves as
  patience 0.

### Requirement: only ci-hf-live turns the window on, with job headroom
The `ci-hf-live` workflow SHALL set `ENGINE_PINS_PATIENCE_SECONDS` on the
`make test-unit-network` battery step to the main pipeline's normal image-push span,
and the hf-live job's `timeout-minutes` ceiling SHALL exceed the window with room for
the battery — so a red is the check's own deadline verdict, never a job timeout.

#### Scenario: the wiring is pinned by a test
- **WHEN** `make test-unit` runs `tests/test_ci_hf_live_workflow.py`
- **THEN** it asserts the battery step carries the numeric knob, the window equals the
  pinned push span, and `timeout-minutes` ≥ window + headroom.
