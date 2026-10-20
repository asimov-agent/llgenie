# The loop's fast suite is a named group in the roster, not a hand-list (issue #403)

**Issue:** [#403](https://github.com/asimov-agent/llgenie/issues/403) · **Change:**
`openspec/changes/unit-suite-fast-group` · **Follows:** the unit-suite aggregator (issue #393,
PR #397), whose doctrine this extends from "the suite" to "a subset of the suite"

## What was wrong

`make test-unit` stopped naming its files when #393 made `scripts/unit_tests.py` discover them. But
`make test` — the loop's stage 6 "full fast suite", the local "done" check — still named its six
hermetic files **by hand on ONE recipe line**:

```
$(TEST_RUN) python -m pytest tests/test_llgenie_serve.py tests/test_lint_linefeeds.py \
  tests/test_kv_quant_bytes.py tests/test_rename_llgenie_serve.py \
  tests/test_fix_loop.py tests/test_fix_bot_sweep.py -p no:cacheprovider -q
```

Same defect as #393: two PRs that touch the fast subset conflict on the same line, and a name
dropped while resolving the conflict silently stops running. The line changed in every commit that
added one of its six files (`e271509`). The fix could not be "run the whole discovered suite": that
takes ~20 minutes and the loop runs `make test` every iteration. The subset had to stay fast — and
the roster had to be the ONE place its files are named.

## What changed

- **`tests/fixtures/unit-suite.json`** gains a `groups` section. `groups.fast` records the six files
  with a `reason`, the `issue` (#403), a `decided` date and the `files` it runs. It is the same
  roster #393 introduced — the one place a test file is named — now carrying a positive selection
  as well as the exclusions.
- **`scripts/unit_tests.py`** learns `--group NAME`: `run --group fast` computes exactly the group's
  files. A group whose file is gone, whose file the roster excludes, whose file list is empty,
  whose file is named twice, or that carries no reason/issue/date is a **finding**; a group a recipe
  asks for that the roster does not record is **fatal** (exit 2, before pytest starts). `list
  --group NAME` and `report` expose it. A group cannot run what the roster keeps out — the two
  halves of the roster agree.
- **The Makefile** `test` recipe runs `python scripts/unit_tests.py run --group fast` and names **no
  test file at all**.
- **`scripts/check_wiring.py`** reads the `--group` argument from a recipe and asks the aggregator
  for that group's list, so `make test` is attributed exactly the group's six files — not the whole
  ~20-minute selection — while `make test-unit` keeps the whole selection. `_aggregator_group`
  accepts both `--group fast` and `--group=fast`.
- **`tests/test_unit_suite.py`** pins the contract: the real roster's group and recipe, the fault
  directions (a gone file, an excluded file, no file, no reason, an unknown group) and the wiring
  attribution of `make test` vs `make test-unit`.
- **`AGENTS.md`** states the rule next to the #393 doctrine: a target that runs a subset of the
  suite does not name its files either — the subset is a named group in the roster.
- **`README.md`** documents the group and the `make test` seam.

## Why "the recipe names no test file" is the whole point

The conflict is not in the test files; it is in the ONE line that lists them. Two changes that add
different tests to the fast subset both edit that line. Moving the list into the roster means each
change edits its own JSON entry — and `check` proves the entry still describes a real, hermetic,
non-empty file set. A name dropped in a bad merge is caught by `check`, not by a silent green gate.

## Verified

- `python3 scripts/unit_tests.py check` → exit 0: `76 of 91 tests/test_*.py selected by discovery;
  15 excluded by tests/fixtures/unit-suite.json; 3 node de-selected; 1 named group(s)`.
- `python3 scripts/unit_tests.py list --group fast` → exactly the six files the recipe named before.
- In `llgenie/test:latest`: `tests/test_unit_suite.py` (13) and `tests/test_wiring.py` +
  `tests/test_check_docs.py` (18) green.
- `python3 scripts/check_wiring.py check` → exit 0 on the real tree.
- `make openspec-validate NAME=unit-suite-fast-group` → exit 0.

## Not covered

- The `excluded` and `deselect` halves of the roster — #393 already covers them.
- The stage roster in `scripts/loop_harness.py` names stages, not files; `make check-wiring` already
  proves each stage target exists and CI reaches it.
