# fake-gh-field-refusal

## Why

`make check-gh-json-fields` (the guard landed for issue #515) validates `gh … --json` field names
statically at scan time, but the bot tests themselves still cannot catch the class: every fake
`gh` in `tests/` answers `--json` requests with a canned blob without ever looking at the requested
names (measured 2026-11-20: 17 test files pair a fake gh with `--json` handling;
`tests/test_auto_merge.py` is the lone fake that validates). A refactor that renames a requested
field therefore passes the whole unit suite green while the real bot dies at the call with
`Unknown JSON field` / exit 1 — exactly the #513 failure shape. This is the deferred end-to-end
half of #515, filed as issue #2975.

## What Changes

- New shared seam `tests/gh_fake.py`: `enforce(argv)` attributes the gh subcommand the same way
  `scripts/check_gh_json_fields.py` does, validates the `--json` field names against
  `tests/fixtures/gh-json-fields.json`, and on violation prints `Unknown JSON field: "<name>"` to
  stderr and exits 1 — reproducing the real gh failure mode inside the test harness.
- A `preamble(tests_dir)` snippet factory so embedded fake-gh scripts (the heredoc'd
  `#!python` files the bot tests write) install the guard in ONE line right after parsing argv.
- Migration: every bot test file whose fake gh answers a `--json` request routes through the seam
  (the embedded guard line, or a direct `gh_fake.enforce` call for function-shaped fakes).
  `tests/test_auto_merge.py`'s existing validation is re-homed onto the same seam without
  weakening its pinned behaviour.
- One red end-to-end pin per migrated leg family: the leg asks for the #513 `authorAssociation`
  shape and its own fake refuses it.

## Impact

- Affected specs: `fake-gh-field-refusal` (new capability, test-harness behaviour).
- Affected code: `tests/gh_fake.py` (new), the fake-gh standups in the bot test files listed in
  `tasks.md`, `tests/test_gh_fake.py` (new). No production (`scripts/`) behaviour changes.
- Depends on: `tests/fixtures/gh-json-fields.json` from main (lands via the PR closing #515);
  this change MUST branch/rebase after that PR merges.
