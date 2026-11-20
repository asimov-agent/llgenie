# gh-json-field-guard

## Why

Issue #513 (#1444's crash) was caught because someone hand-pinned ONE invalid field name
(`authorAssociation` on `gh pr view`) in ONE script via `tests/fixtures/gh-pr-view-fields.json`
(issue #514). The same class is live elsewhere and unguarded: a `gh <cmd> --json <fields>` call
asking for a field the real CLI does not have makes gh refuse the WHOLE call (exit 1), the bot
catches the crash silently, and `make test-unit` never notices because the fake gh in tests does
not validate field names. The scan for issue #515 measured 19 scripts passing `--json` with 46+
call sites; only the pinned pr-view site was checked.

While building this guard, it found the class live in the committed tree:
`.github/workflows/registry-liveness.yml` called `gh issue create … --json number --jq .number` —
the real CLI has NO `--json` flag on `issue create` at all (measured: `unknown flag: --json`,
exit 1), and the surrounding `2>/dev/null` swallowed the failure, so the lane's tracking-issue
filing silently never worked.

## What Changes

- ADD `scripts/check_gh_json_fields.py`: a static guard that scans every `scripts/*.py` (AST:
  gh argv lists, constant and `",".join(<const>)` field resolution) and every `.github/workflows/*.yml`
  shell lane (`gh <cmd> --json …` regex) and fails when a requested field is not in the
  per-subcommand allowlist captured from the REAL gh CLI. It fails CLOSED: a `--json` that cannot
  be attributed to a known subcommand, or whose field list is not statically resolvable, is a
  finding — never a skip.
- ADD `tests/fixtures/gh-json-fields.json`: per-subcommand field allowlists captured live from
  `gh <cmd> --json __probe__` for the seven subcommands the repo uses (`pr view`, `pr list`,
  `pr checks`, `issue view`, `issue list`, `run view`, `run list`).
- ADD make target `check-gh-json-fields` (mk/gates.mk), wired into `ci_unit.MAKE_SEQUENCE` after
  `make check-ci-discipline`, classified in `scripts/issue_bot_gates.py` DEFERRED, grouped in
  `scripts/package-layers.json`.
- FIX `registry-liveness.yml`: `gh issue create` no longer passes `--json number --jq .number`
  (the verb has no `--json`); the created issue number is taken from the URL gh prints.
- ADD `tests/test_check_gh_json_fields.py` with the #513 `authorAssociation` shape pinned as a
  red case, fail-closed controls, shell-lane cases, and a green-against-the-real-tree coverage
  test.

## Impact

- Affected specs: `gh-json-field-guard` (new capability)
- Affected code: `scripts/check_gh_json_fields.py` (new), `tests/fixtures/gh-json-fields.json`
  (new), `mk/gates.mk`, `scripts/ci_unit.py`, `scripts/issue_bot_gates.py`,
  `scripts/package-layers.json`, `.github/workflows/registry-liveness.yml`,
  `tests/test_check_gh_json_fields.py` (new), `tests/test_ci_unit_stage.py`
- Issue: #515. No bot behaviour is rewritten: the guard validates call sites; the one workflow fix
  repairs a call site the guard proved was already broken.
