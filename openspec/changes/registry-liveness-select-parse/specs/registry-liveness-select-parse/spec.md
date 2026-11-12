# registry-liveness-select-parse

## MODIFIED Requirements

### Requirement: the dispatch reads all four `[select]` fields with the marker in its own variable

The gate's machine-readable selection line is `[select] <engine> <variant> <tag-suffix>`
(4 whitespace-separated fields; the committed engine id, dots intact). The
`registry-liveness` dispatch loop MUST read all four into distinct variables, with the
`[select]` marker occupying its own first field, so the engine id is never shifted into
the marker slot. The dispatch MUST forward `engine=<committed id, dots intact>`,
`arch=<variant>` and `push=true` to `engine-build`.

WHEN the read loop binds fields from a `[select]` line
THEN the first binding is the `[select]` marker (not the engine id), the second is the
committed engine id, the third the variant, and the fourth the tag suffix
AND the engine id reaches `engine-build` dots intact — never the `none/none` placeholder
a shifted parse produces.

#### Scenario: a correctly-formatted line dispatches four named cells

- **Given** a `[select]` line `[select] llama.cpp cpu 7d7f0287-1b5db7a2-cpu`
- **When** the `registry-liveness` dispatch loop binds it
- **Then** `engine="llama.cpp"`, `arch="cpu"`, `push=true` and the command names
  `llama.cpp/cpu (missing tag 7d7f0287-1b5db7a2-cpu)`
- **Test:** `tests/test_check_engine_pins_published.py::test_the_liveness_dispatch_reads_all_four_select_fields`
  (the gate's emitted line format and the workflow's read loop are locked to the same
  4-field shape)

### Requirement: a malformed select line is skipped loudly, never dispatched

A line whose first field is not exactly `[select]`, or that lacks the four cell fields,
MUST be skipped loudly (an `unrecognized select line` / `malformed select line` message
naming the line) and MUST NOT be dispatched — a shifted parse must never reach
`engine-build` with a placeholder engine.

WHEN the dispatch loop meets a line that is not a well-formed `[select]` line
THEN it prints a loud refusal naming the fields it saw and does not call `gh workflow run`.

#### Scenario: a shifted 3-field line is refused before dispatch

- **Given** the pre-fix failure line `[select] llama.cpp cpu 7d7f0287-1b5db7a2-cpu`
  being read by a 3-variable loop (the bug itself)
- **When** the guarded loop reads a line whose marker field is not exactly `[select]`,
  or which lacks the four cell fields
- **Then** a loud `not dispatching` message is printed and no dispatch fires
- **Test:** asserted by the guard text in
  `tests/test_check_engine_pins_published.py::test_the_liveness_dispatch_reads_all_four_select_fields`
  (`unrecognized select` / `not dispatching` must be present in the workflow)

### Requirement: the workflow's read loop cannot drift from the gate's line format

A test MUST read both the gate's `[select]` format string and the workflow's
`while read -r` loop and assert they agree on field count and binding order, so a future
change to one surface cannot silently break the other.

WHEN either the gate's selection line shape or the workflow's read binding changes
THEN the matching unit test fails, naming the drift.

#### Scenario: a 3-variable read loop reds the guard

- **Given** the gate emits a 4-field `[select]` line and the workflow binds it with only
  three `read` variables
- **When** the guard test inspects the workflow's `while read -r` fields
- **Then** it fails: a 4-field read with the marker named in its own first field is
  required
- **Test:** `tests/test_check_engine_pins_published.py::test_the_liveness_dispatch_reads_all_four_select_fields`
