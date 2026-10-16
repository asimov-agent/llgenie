# 2026-10-16 — inline-check-all-steps (#305)

## The defect

`workflow-inline-scripts` — the check #296/PR #299 fixed to scan *per command* — only ever saw **one
step per workflow**. `_steps()` started a new block on each `run:` line but only ended one on a line
with no leading whitespace. A workflow nests every line under `jobs:`/`<job>:`/`steps:`, so that never
happens: the loop kept extending the same block, each new `run:` silently dropped the previous one, and
only the file's last block reached the end-of-function append.

Measured over the committed workflows: `ci.yml` 1 vs 20 real blocks; **13 of 105** blocks total. The
per-command rule from #299 was therefore enforced on 12% of the tree, and its "the real tree has no
inline script call" test proved only that each workflow's *last* block was clean.

## The fix

- `_steps()` ends a `run:` block at the first non-blank line indented at or below the `run:` line — the
  YAML structure — so every step is returned. 13 → 105 blocks.
- Scanning every step surfaces a real false positive: `fix-bot.yml` writes
  `... (scripts/fix_loop.sh): the check ran ...` into a multi-line `git commit -am "…"` message. That is
  prose. `_code_only()` strips quoted strings but keeps `$( ... )`/backtick substitutions, so the commit
  message is not filed while `gap="$(python3 scripts/engine_skill_gap.py …)"` still is. Without this,
  the wider scan would have traded a false negative for a false positive.
- Three tests pin both directions and the guard; two of them fail against the pre-fix code.

## Verification

- `_steps()` 13 → 105 over the real workflows; real tree 0 findings (and 0 prose false positives).
- `tests/test_code_review.py` → 29 passed in `llgenie/test:latest`.
- `make openspec-validate NAME=inline-check-all-steps` → valid; fast gates → see the PR's checks.

## Status

Implemented in the `feat/inline-all-steps` branch; PR pending. Closes #305.

Related: #296 / #299 (the per-command fix this completes the coverage of), #293 (the same tool's "does
not look at open PRs" blind spot), #317 (the loop's Linux `test` stage, fixed by PR #322).
