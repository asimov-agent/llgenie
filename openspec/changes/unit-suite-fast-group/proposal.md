# unit-suite-fast-group — proposal

Issue: [#403](https://github.com/asimov-agent/llgenie/issues/403)

## Why

`make test-unit` no longer names its test files — `scripts/unit_tests.py` discovers them (issue
#393, PR #397). But `make test` — the loop's stage 6 "full fast suite", the local "done" check —
still did:

```
$(TEST_RUN) python -m pytest tests/test_llgenie_serve.py tests/test_lint_linefeeds.py \
  tests/test_kv_quant_bytes.py tests/test_rename_llgenie_serve.py \
  tests/test_fix_loop.py tests/test_fix_bot_sweep.py -p no:cacheprovider -q
```

Six file names on ONE recipe line. It is the same defect #393 closed for `make test-unit`: two PRs
that touch the fast subset conflict on the same line, and a name dropped while resolving the
conflict silently stops running. That line has changed in every commit that added one of its six
files (git blame: `e271509`).

The fix cannot be "run the whole discovered suite": the full suite takes ~20 minutes, and the loop
runs `make test` on every iteration. The fast subset has to stay fast — so it belongs in the roster
as a named group, not in the Makefile.

## What Changes

- **`tests/fixtures/unit-suite.json`** gains a `groups` section. `groups.fast` records the six
  files with a `reason`, the `issue`, a `decided` date and the `files` it runs. The roster is the
  ONE place a test file is named, exactly as #393 established for exclusions.
- **`scripts/unit_tests.py`** learns `--group NAME`: `run --group fast` computes the group's files
  instead of the whole selection. The group is validated like every other roster decision — each
  file must exist and be in the hermetic selection (a group cannot run what the roster keeps out),
  the group must name a file and carry its reason/issue/date, and an unknown group is fatal (exit 2)
  so a target asking for a group nobody recorded cannot silently run nothing. `list --group NAME`
  and `report` expose it.
- **`make test`** becomes `python scripts/unit_tests.py run --group fast` — no file names, so two
  PRs that touch the fast subset never edit the same line again.
- **`scripts/check_wiring.py`** attributes only the group's files to `make test`, not the whole
  selection: `_aggregated` reads the `--group` argument from the recipe and asks the aggregator for
  that group's list. Otherwise `make test` would claim to run the ~20-minute suite.
- **`tests/test_unit_suite.py`** pins the group contract: the real roster's group, the fault
  directions (a gone file, an excluded file, no file, no reason, an unknown group), and the wiring
  attribution.
- **`AGENTS.md`** states the rule: a subset a target runs is a named group in the roster, never a
  hand-list in a recipe.
- **`README.md`** documents the group and the command; `agent-wiki/` records the change.

## Not covered

- The `deselect` and `excluded` halves of the roster are unchanged — #393 already covers them.
- The stage rosters in `make chained` / `scripts/loop_harness.py` name stages, not files, and
  `make check-wiring` already proves those targets exist and CI reaches them.
