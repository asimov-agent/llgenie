# Change: bot-stamp-roster-2110

## Why

Issue #2110: the architecture bot is the sixth bot PR producer and the one the #2050 stamp change never
converted. It composes its PR body with a restated copy of the pair (`_hygiene_lines`,
`scripts/architecture_bot.py:451`) instead of calling the one stamp authority
(`bot_preflight.stamp_body`/`resolve_record`), and
`tests/test_bot_stamp_body.py::test_every_bot_pr_producer_stamps_before_it_opens_or_edits` pins a
hardcoded five-producer list, so the gap — and any future unstamped producer — is invisible to the
suite. Merged arch PRs today (e.g. #2629) carry the pair only because the producer hand-rolls it.

## What Changes

- `architecture_bot` stamps through the one authority: `publish` resolves the record via
  `bot_preflight.resolve_record(root)` BEFORE any GitHub write, branch, or commit (a checkout without a
  resolvable `main` ref refuses, naming the refs it tried), and both the real PR body and the `--dry`
  preview body are run through `bot_preflight.stamp_body`. `_hygiene_lines` is deleted — no restated
  copy remains.
- `test_bot_stamp_body` derives its producer roster from the tree instead of a hardcoded list: every
  `scripts/*.py` that carries a real `gh pr create` call must contain the `bot_preflight.stamp_body`
  call, and every workflow whose non-comment steps run `gh pr create` must run `make bot-stamp-body`
  before it. A synthetic unstamped module in a scratch tree must be named by the derived roster (the
  negative control that proves a new unstamped producer reds `make test-unit`).
- `tests/test_architecture_bot.py` measures the real gate: the publish body's
  `check_pr_hygiene.pr_agents_line_findings` verdict is `[]`, and the same body with the pair stripped
  yields `agents-line`; `publish` refuses when no `main` ref resolves, before it touches GitHub.
- `docs/BOTS.md` lists the architecture bot beside the stamped producers.

## Impact

Affected specs: `bot-body-stamp` (new capability delta)
Affected code: `scripts/architecture_bot.py`, `tests/test_bot_stamp_body.py`, `tests/test_architecture_bot.py`, `docs/BOTS.md`
