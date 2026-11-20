# gh-json-field-guard — the #513 class guarded structurally (issue #515)

Date: 2026-11-20. Landed on branch `feat/gh-json-field-guard-515`.

## What was verified against the spec

- **The guard is structural, not pinned.** `scripts/check_gh_json_fields.py` scans every
  `scripts/*.py` (AST: gh argv lists, constants, `",".join(<const>)` field assembly) and every
  `.github/workflows/*.yml` shell lane for `gh … --json <fields>` and validates each field name
  against `tests/fixtures/gh-json-fields.json` — per-subcommand allowlists captured live from the
  real CLI (`gh <cmd> --json __probe__`, seven subcommands). At the pushed head the tree measures
  **39 scripts, 98 call sites, 0 findings** (issue #515 measured 19/46+; the roster has grown).
- **It fails CLOSED.** A `--json` not attributable to a known subcommand
  (`unattributable-subcommand`) and a `--json` whose fields are not statically resolvable
  (`unresolvable-fields`, e.g. shell `--json "$FIELDS"`) are findings, not skips — proven by
  synthetic red cases in `tests/test_check_gh_json_fields.py`.
- **The guard found a live bug while being built.** `registry-liveness.yml` ran
  `gh issue create … --json number --jq .number`; the real CLI has no `--json` on `issue create`
  (measured `unknown flag: --json`, exit 1) and `2>/dev/null` swallowed it — the lane's
  tracking-issue filing silently never worked. Fixed in the same change: the number is now taken
  from the URL `gh issue create` prints (`sed -E 's#.*/issues/##'`).
- **Wiring.** `make check-gh-json-fields` (mk/gates.mk) inserted into `ci_unit.MAKE_SEQUENCE`
  after `make check-ci-discipline`, classified in `issue_bot_gates.DEFERRED`, grouped in
  `scripts/package-layers.json`; `tests/test_ci_unit_stage.py` updated (sequence, roster, dry-run
  count 54).
- **Gates run:** `make -s check-gh-json-fields` rc=0; targeted pytest (4 new-file tests +
  ci_unit_stage + package_layers + issue_bot_gates) 44 passed rc=0;
  `make openspec-validate NAME=gh-json-field-guard` rc=0; `make lane-preflight` → `preflight: OK`;
  full unit battery rc=0 (see PR CI for the exact head shas).

## Key decisions

- `gh issue create` is deliberately NOT added to the allowlist: its lack of `--json` is exactly
  what the guard must keep flagging.
- Owned repo scripts with their own `--json`-style flags are out of scope (false-positive control
  test pins this).
- No bot behaviour rewritten: the guard validates call sites; the one workflow edit repairs a call
  site the guard proved was already broken.

## Current status

Issue #515 closes with the PR; the guard is a standing ci-unit gate from this head on.
