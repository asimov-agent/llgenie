# inline-check-all-steps — proposal

Issue: [#305](https://github.com/asimov-agent/llgenie/issues/305)

## Why

`scripts/code_review.py`'s `workflow-inline-scripts` check — the reviewer bot's "every command a CI
workflow runs must be a make target" rule — was fixed to scan **per command** in #296/PR #299. But it
only ever *saw* one step per workflow: `_steps()` started a new `run:` block on every `run:` line and
only ended one on a line with no leading whitespace. A workflow nests every line under
`jobs:`/`<job>:`/`steps:`, so that condition is never true — the loop kept extending the same block and
each new `run:` silently dropped the previous one. Only the file's last block survived to the
end-of-function append.

Measured over the committed workflows: `ci.yml` has 20 real `run:` blocks and `_steps()` returned 1.
Across all 13 workflows, **13 of 105 blocks** were being inspected — so the per-command rule was
enforced on 12% of the tree. The check's own "the real tree has no inline script call" test proved only
that each workflow's *last* block was clean.

## What changes

- **`_steps()` extracts every step.** A `run:` block now ends at the first non-blank line indented at or
  below the `run:` line itself — the YAML structure, not "no leading whitespace".
- **The per-command scan distinguishes a command from prose.** Scanning every step surfaces
  `fix-bot.yml`'s commit message, which quotes `scripts/fix_loop.sh` inside a multi-line `git commit -am
  "…"` string. That is a message, not a command. `_code_only()` strips quoted prose but keeps `$( ... )`
  and backtick substitutions, so `gap="$(python3 scripts/engine_skill_gap.py …)"` is still a finding
  while the commit message is not. Without this, #305's "scan every step" would trade one false
  negative for one false positive.
- **Tests** pin both directions: a violation in a step that is not the last one is a finding; a script
  name quoted as a message is not; a script in a substitution still is.

## Verification (real output)

- **Pre-fix vs. fixed, measured over the real tree**: `_steps()` yields **13** blocks pre-fix and **105**
  post-fix; with the pre-fix extractor the real tree reports **0** findings (a violation in any earlier
  step is invisible), with the fixed one it still reports **0** — because the tree is genuinely clean
  and the two prose false positives are now excluded.
- **The two regression tests fail against the pre-fix code** and pass against the fix — both directions
  of #305 are pinned, not just "the tree is green".
- `tests/test_code_review.py` → **29 passed** in `llgenie/test:latest`.
- `make lint`, `make check-wiring`, `make check-docs`, `make check-dispatch-forms` and
  `make openspec-validate NAME=inline-check-all-steps` → see the PR's checks.

## Not covered

- #293 — the reviewer bot does not look at open PRs (a different blind spot in the same tool).
- #317 — the loop's `test` stage on Linux; a separate defect, fixed by PR #322.

Refs: #296, #299 (the per-command fix whose coverage this completes).
