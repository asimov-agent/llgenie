# tasks — gh-json-field-guard (#515)

## 1. Guard

- [x] 1.1 Write `scripts/check_gh_json_fields.py`: AST scan of `scripts/*.py` (constants,
      `",".join(<const>)`, fail-closed unattributable/unresolvable findings) plus shell-lane regex
      scan of `.github/workflows/*.yml`
- [x] 1.2 Capture the per-subcommand allowlists from the real CLI into
      `tests/fixtures/gh-json-fields.json` (`gh <cmd> --json __probe__`, seven subcommands)

## 2. The live finding the guard made

- [x] 2.1 Fix `.github/workflows/registry-liveness.yml`: drop `--json number --jq .number` from
      `gh issue create` (measured: `unknown flag: --json`, exit 1 — the failure was swallowed by
      `2>/dev/null`); take the number from the printed issue URL

## 3. Wiring

- [x] 3.1 Add `check-gh-json-fields` to `mk/gates.mk`
- [x] 3.2 Insert it into `ci_unit.MAKE_SEQUENCE` after `make check-ci-discipline` and update
      `tests/test_ci_unit_stage.py` (sequence + roster + dry-run count)
- [x] 3.3 Classify it in `scripts/issue_bot_gates.py` `DEFERRED` with a reason
- [x] 3.4 Group `check_gh_json_fields` in `scripts/package-layers.json`

## 4. Tests

- [x] 4.1 `tests/test_check_gh_json_fields.py`: the #513 `authorAssociation` shape pinned red,
      const-join red, fail-closed red cases, shell-lane cases, owned-`--json` false-positive
      control, fixture/allowlist consistency, and the green real-tree coverage test

## 5. Verification (proofs replayable at the pushed head)

- [x] 5.1 `make -s check-gh-json-fields` on the tree → `0 finding(s)`, rc=0 (measured at
      39 scripts / 98 call sites)
- [x] 5.2 `pytest tests/test_check_gh_json_fields.py tests/test_ci_unit_stage.py
      tests/test_package_layers.py tests/test_issue_bot_gates.py` → 44 passed, rc=0
- [x] 5.3 `make openspec-validate NAME=gh-json-field-guard` → rc=0
- [x] 5.4 `make lane-preflight` on the committed tree → `preflight: OK`
