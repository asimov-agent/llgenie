# unit-suite-aggregator — proposal

Issue: [#393](https://github.com/asimov-agent/llgenie/issues/393)

## Why

`make test-unit` names its pytest files **by hand** — all 74 of them, on one recipe line
(`Makefile:924-925`). The tree holds 89 `tests/test_*.py`; the other 15 run from their own
targets (host, image, network, Metal). Adding one hermetic test therefore means editing that
single shared line, and the cost is measurable on `main` (`f91d82f`):

- the test-unit file list **changed in 63 of the last 300 commits** (21%); 96 of those 300
  touch the Makefile at all;
- two PRs that add unrelated tests conflict on the same line, so the merge queue serialises
  them for no reason and every conflict is resolved by hand on a line where a dropped name is
  invisible;
- a name lost that way is a test that **silently stops running** — the gate stays green
  because the assertion never executed, which is the failure shape `AGENTS.md` forbids;
- the enumeration is duplicated into the tests: **7 files assert their own name is in that
  recipe** (`tests/test_agent_nerve.py:677`, `tests/test_check_docs.py:233`,
  `tests/test_engine_bump.py:1872` and `:1904`, `tests/test_engine_skill_gap.py:549`,
  `tests/test_issue_implementer.py:229`, `tests/test_secret_output.py:308`,
  `tests/test_wiring.py:230`), so it cannot be retired in one place either.

The sibling repo (`trending-local-llms`, same author) already works the other way: its unit
entry is ONE aggregating call — `make test` → `python3 -m pytest tests/ -q` — so a new
`tests/test_*.py` joins the suite by discovery with no shared line to edit, and the checks that
need real network or hardware live in their own targets (`validate-fetch`, `search-smoke`,
`model-caps`, `hermes-smoke`). llgenie has the same shape available and does not use it.

## What Changes

- **`scripts/unit_tests.py`** — the ONE aggregator of the hermetic unit suite. It discovers
  `tests/test_*.py` and subtracts `tests/fixtures/unit-suite.json`, a dated roster of the files
  deliberately NOT in it (reason + the issue + the target that runs them instead). The suite is
  therefore **fail-closed by discovery**: a new test file is in the gate the moment it exists,
  and an exclusion has to be a decision.
  - `list` — the selection, one path per line;
  - `argv` — the exact pytest invocation `run` execs;
  - `check` — the roster is consistent (exit 1 with the finding): an entry whose file is gone,
    an entry missing its reason / issue / date / target, an entry whose target is not a make
    target or whose recipe does not name the file, a deselection whose test no longer exists,
    or an empty selection;
  - `run` — `check`, then exec pytest with the discovered files and the roster's `--deselect`
    node ids (never a `-k` substring expression, where a new test whose name CONTAINS a
    deselected name is silently dropped).
- **`make test-unit`** becomes `python scripts/unit_tests.py run` — one line, no file names, so
  two PRs that add tests never touch the same line again.
- **`scripts/check_wiring.py`** learns the discovery seam: a `tests/test_*.py` the aggregator
  selects is wired by the target that runs the aggregator, and the roster's consistency findings
  are part of the wiring graph — so the new direction is guarded too (a file excluded from the
  unit suite must still be named by a target CI reaches, or be a recorded decision).
- **The 7 self-wiring assertions** point at the aggregator's selection instead of a recipe line,
  and the two `tests/test_engine_bump.py` cases read the deselections from the roster.
- **`AGENTS.md`** states the rule: the unit suite is aggregated, never enumerated.
- **`README.md`** documents the seam, the roster and the report command; `agent-wiki/` records
  the change.

## Not covered

- `scripts/check_wiring.py json` — the third subcommand reads `g["named_by_target"]`, a key
  `graph()` never returns, so it exits 1 on a healthy tree and has never worked. Nothing calls
  it; it is its own defect and its own issue: [#395](https://github.com/asimov-agent/llgenie/issues/395).
- The `.PHONY` block — the same hand-edited shared-block class of defect (22 of 176 targets
  undeclared, so a file with a target's name makes the target a green no-op). Filed as its own
  issue: [#392](https://github.com/asimov-agent/llgenie/issues/392).
- The stage rosters in `make test` / `make chained` / `scripts/loop_harness.py` stay as they are:
  they name stages, not files, and `make check-wiring` already proves those targets exist and CI
  reaches them.
