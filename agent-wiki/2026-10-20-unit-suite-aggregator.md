# The hermetic unit suite is discovered, never enumerated (issue #393)

**Issue:** [#393](https://github.com/asimov-agent/llgenie/issues/393) · **Change:**
`openspec/changes/unit-suite-aggregator` · **Mirrors:** the sibling repo `trending-local-llms`,
whose unit entry is one aggregating call with the network/hardware checks in their own targets

## What was wrong

`make test-unit` named its 74 pytest files **by hand** on ONE recipe line. Two PRs that added
unrelated tests conflicted on the same line, and a name lost while resolving that conflict
silently stopped running. Measured on `main` (`f91d82f`): the file list changed in **63 of the
last 300 commits** — the single most conflict-prone line in the tree. The 15 files deliberately
kept out of the gate (native-Metal engines, the installed-launcher checks) were kept out by
*omission*, not by a recorded decision, so nothing proved they still ran in their own targets.

## What changed

- **`scripts/unit_tests.py`** — the ONE place the suite is computed. It discovers every
  `tests/test_*.py` MINUS the files `tests/fixtures/unit-suite.json` records as deliberately not
  hermetic (each with its reason, its issue, its date and the target that runs it instead). A new
  test file is in the gate the moment it exists — there is no shared line to edit.
- **`tests/fixtures/unit-suite.json`** — the 15 dated exclusions and the 3 node de-selections of
  the live TensorFold release reads. A missing roster is a LOUD failure, never a silent empty one.
- **The Makefile** `test-unit` recipe runs `python scripts/unit_tests.py run` and names **no test
  file at all**.
- **`scripts/check_wiring.py`** asks the aggregator what it selects, so a discovered file is wired
  through the target that runs it; `make wiring-report` shows the seam. The aggregator's own
  consistency findings join the graph.
- **`tests/test_unit_suite.py`** covers the spec's scenarios against the real tree and real scratch
  trees: discovery, the roster's staleness in every direction, the exact `--deselect` node-id
  invocation, `run` refusing to start on a broken roster.
- **The 9 self-wiring assertions** (`test_agent_nerve.py`, `test_agent_shell_keys.py`,
  `test_check_docs.py`, `test_engine_bump.py`, `test_engine_skill_gap.py`, `test_issue_implementer.py`,
  `test_require_env.py`, `test_secret_output.py`, `test_wiring.py`) now read the aggregator's
  selection instead of the recipe line, so they keep proving the file runs after this change. The
  first full-suite run found the last two (`test_agent_shell_keys.py`, `test_require_env.py`): they
  asserted the file name anywhere in the Makefile text, which the discovery change removes.

## Why exact node ids, never `-k`

The roster's `deselect` entries become `--deselect file::test` node ids. A `-k` expression matches
substrings, so a new test whose name CONTAINS a deselected test's name would be silently dropped
from the gate. `-k 'not test_derive_reports_the_live_release_archives'` would also drop a future
`test_derive_reports_the_live_release_archives_hermetic`. Exact ids cannot.

## Verified

- In `llgenie/test:latest`: the full discovered suite (`scripts/unit_tests.py run`) is green, and
  the 8 changed/new test files pass (255 passed).
- `python3 scripts/check_wiring.py check` → exit 0 on the real tree, and the report names the seam:
  `discovery: make test-unit runs 75 file(s) through scripts/unit_tests.py without naming them in its recipe`.
- `python3 scripts/unit_tests.py check` → exit 0: `75 of 90 tests/test_*.py selected by discovery; 15
  excluded by tests/fixtures/unit-suite.json; 3 node de-selected`.
- The selection the aggregator computes is **identical** to the 74 files the recipe named before the
  change — the refactor moves the list, it does not move the gate.
- `make lint`, `make openspec-validate NAME=unit-suite-aggregator` pass on the host.

## Not covered

- The `.PHONY` block — the same hand-edited shared-block class of defect (22 of 176 targets
  undeclared). Its own issue: [#392](https://github.com/asimov-agent/llgenie/issues/392).
- `scripts/check_wiring.py json` — the subcommand reads a key `graph()` never returns, so it exits 1
  on a healthy tree. Its own issue: [#395](https://github.com/asimov-agent/llgenie/issues/395).
