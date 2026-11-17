## ADDED Requirements

### Requirement: Lane script controls ship beside their subjects
Every detector in `agents/llgenie-pr-merge-conflict/scripts/` that has a live positive/negative
control SHALL carry that control in the same lane-tree `scripts/` directory, byte-identical to the
live copy, so `make provision-agent-profiles` never ships an untested detector (#2090, #2883).

#### Scenario: controls are census-`same`
- **Given** the live profile root `scripts/` carries `test-dirty-detector.py` and `test-tally-delta.py`
- **When** the fold census runs at the shipped head
- **Then** both files are reported `same` and the live-only row count drops by two (13 -> 11)

#### Scenario: controls run green against the shipped detectors
- **Given** the tree copies sit beside `dirty-detector.py` and `tally-delta.py`
- **When** each control is run host-side with `python3 agents/llgenie-pr-merge-conflict/scripts/test-*.py`
- **Then** the detector control reports 4/4 PASS and the tally control reports 16/16 PASS, each exiting 0
