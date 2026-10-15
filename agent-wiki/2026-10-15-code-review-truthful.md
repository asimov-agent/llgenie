# 2026-10-15 — issue #307: the code-review bot's report must equal what it files

Part of the "exercise every bot dispatcher one at a time" sweep: `code-review-bot.yml` had never
run, so it was dispatched (`workflow_dispatch`, `dry=true`) and its output read. Two defects.

## What was done

- OpenSpec change `code-review-truthful` created FIRST via the containerized CLI
  (`make openspec-new`), validated (`openspec-validate` exit 0), all tasks ticked.
- `scripts/code_review.py`: new `_without_comments()` strips full-line `#` comments;
  `check_secrets_not_defined` now matches `secrets.X` against the comment-stripped text (like
  `check_workflow_inline_scripts` already does via `_steps`). A `secrets.X` that lives only in a
  comment (e.g. `rebase-bot.yml:93`, a doc example) is no longer filed as an undefined secret.
- `.github/workflows/code-review-bot.yml`: the `Scan the tree and the pipelines` step now carries
  `GH_TOKEN: ${{ secrets.BUMP_TOKEN || github.token }}`, the same as the filer step. Both call the
  same checks, so the tokenless scan printed `no findings` while the filer found 3 (run
  [38825474696](https://github.com/asimov-agent/llgenie/actions/runs/38825474696)).
- `tests/test_code_review.py`: two new tests — a commented `secrets.X` is not a finding, and the
  scan step carries the same `GH_TOKEN` as the filer.

## Verified

- Ran `tests/test_code_review.py` in `llgenie/test:latest` (`:ro` mount): 23 passed.
- Rule 6c: the two new tests FAIL on the pre-fix tree (`git show origin/main:...` into a scratch
  root) and pass after — `2 failed, 1 passed`.
- `make code-review-scan` on current `main` with a token still reports the two REAL findings
  (`issue-refiner.yml` reads `secrets.OPENROUTER_API_KEY` / `secrets.OPENCODE_API_KEY`, neither
  defined) and no longer the bogus `secrets-not-defined/X`.

## Status

- Branch `fix/code-review-truthful`, PR [#308](https://github.com/asimov-agent/llgenie/pull/308) against
  `asimov-agent/llgenie:main`, `closes #307`.
- Not covered (separate): the two real `issue-refiner.yml` undefined-secret findings, and #305
  (the inline-script check only inspects the last `run:` block).
