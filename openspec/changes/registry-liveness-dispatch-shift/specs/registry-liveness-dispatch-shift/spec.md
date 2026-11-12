# registry-liveness-dispatch-shift

## ADDED Requirements

### Requirement: the dispatch loop binds the `[select]` contract fields positionally

The registry-liveness dispatch step MUST read the gate's contract line
`[select] <engine> <variant> <tag-suffix>` with the marker in its OWN variable, so that
`-f engine=` receives the committed engine id (dots intact) and `-f arch=` receives the variant.
A line that does not match the contract exactly — marker missing, a required field empty, or a
fifth token present — MUST be printed, MUST NOT be dispatched, and MUST fail the step with a
non-zero exit naming the violation.

#### Scenario: a contract line dispatches the committed cell

- **Given** a `select.txt` line `[select] llama.cpp cpu 7d7f0287-1b5db7a2-cpu`
- **When** the dispatch step runs
- **Then** `gh workflow run engine-build.yml` is called with `engine=llama.cpp`, `arch=cpu`,
  and `push=true`

#### Scenario: a malformed line is refused, not dispatched

- **Given** a `select.txt` line whose first token is not `[select]`, or that has an empty
  engine/variant/tag, or a fifth token
- **When** the dispatch step runs
- **Then** the step prints `UNRECOGNIZED select line` with the raw text, dispatches nothing for
  that line, and exits 1 after the loop

#### Scenario: the workflow fields cannot drift from the gate's line format

- **Given** the gate's line contract printed by `scripts/check_engine_pins_published.py`
- **When** the unit suite runs
- **Then** a test asserts the workflow's `while read` field list binds the marker separately
  and matches the four-token contract
