# 2026-10-19 — the secret-output guard catches the two whole-stdout shapes (#361)

Implements [#361](https://github.com/asimov-agent/llgenie/issues/361), a child of the bot-fleet parent
[#357](https://github.com/asimov-agent/llgenie/issues/357). OpenSpec change: `openspec/changes/secret-whole-stdout`.

## What was wrong (measured)

`scripts/check_secret_output.py` was a fork of the sibling repo's guard behind by three rule families
(223 lines vs 459): `${{ github.token }}` in a `run:` block was not caught at all, and neither were the
two shapes a bot pipeline produces when it publishes output — a whole stdout into `$GITHUB_OUTPUT`
(which fails a step with `Invalid format` after the work is done) and a whole stdout into the job log
via `tee /dev/stderr` (where only *registered* values are masked).

## What changed

- `secrets-in-run-block` also matches `${{ github.token }}` / `${{ github['token'] }}` /
  `${{ github["token"] }}` inside a `run:` block.
- New `whole-stdout-into-output-file` and `whole-stdout-into-log` rules, with the sibling's rule names.
- The pipe rule requires a **single** `|`: llgenie's workflows use `a || b` shell-or chains that end in
  `>> "$GITHUB_OUTPUT"`, and the sibling's loose pattern flagged three real lines when ported. Measured,
  then fixed with lookarounds — the port is a strict improvement on the copy.
- `tests/test_secret_output.py`: one planted fixture per rule plus one safe counter-shape per rule
  (`env:`-passed `github.token`, the quoted computed writer, `tee /tmp/out.log`), so the rule cannot be
  loosened to green and the safe forms cannot start failing.
- README rule table (two new rows + the widened run-block row).

## Verified

`pytest tests/test_secret_output.py -q` → 28 passed (21 before, 7 new + the tree-wide check, which
still reports nothing). `make check-secret-output`, `make check-wiring`, `make check-docs`, `make lint`,
`make openspec-validate NAME=secret-whole-stdout`.

## Follow-ups

- The value scanner (gitleaks) is #360; the redacted run log is #359 (PR #366); the credential seam is
  #358 (PR #365). The `whole-stdout-into-log` rule is what makes an unredacted upload catchable, which
  is why it lands alongside #359's seam.
