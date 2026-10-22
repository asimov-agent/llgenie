# 2026-10-22 — auto-merge asks `gh` only for fields it has (#513)

**Issue:** [#513](https://github.com/asimov-agent/llgenie/issues/513) · **PR:** see the PR that closes it

## What was broken

The `auto-merge` workflow (`.github/workflows/auto-merge.yml`, built by #482 and moved to `workflow_run` by #493)
has never merged a PR. Run [`39769182946`](https://github.com/asimov-agent/llgenie/actions/runs/39769182946), PR
#511's green run:

```
[auto-merge] gh pr view 511 … --json …,author,authorAssociation,reviewDecision failed (1):
             Unknown JSON field: "authorAssociation"
```

`gh pr view --json` has no `authorAssociation` field. `pr_state` asked for it in the one call every decision is
built from, so `auto_merge.py` exited 2 before `decide()`: no merge, no deferral comment. The token was present
(`GH_TOKEN: ***`), the PR resolution was correct — the gate died on its own argument list.

Measured: every recent merge on `main` is `mergedBy=andyholst` (#511 … #481), and every `auto-merge` run in the
workflow's history is `failure` or `skipped`.

## Why the suite missed it

`tests/test_auto_merge.py`'s fake `gh` answered `pr view` with the JSON blob it was handed and never looked at the
requested field names, so an invented name was invisible to the whole unit suite.

## What changed

- `scripts/auto_merge.py`: `PR_VIEW_FIELDS` is one constant joined into the single `gh pr view --json` call;
  `authorAssociation` removed. `is_bot_login()` decides the #511 bot rule from the login alone
  (`github-actions[bot]`, `app/github-actions`, `…[bot]`, `app/…`).
- `tests/fixtures/gh-pr-view-fields.json`: `gh`'s own allowlist, captured from `gh pr view 511 --json __probe__`
  (gh 2.102.1).
- `tests/test_auto_merge.py`: a test asserts every requested field is in that allowlist, a test covers the
  login-only bot rule, and the fake `gh` now refuses an unknown field exactly as the real CLI does — so every
  end-to-end case in the file fails on a regression of this class.
- `README.md`: the field-list rule is documented next to the auto-merge contract.

## Verified

- `python -m pytest tests/test_auto_merge.py` (container `llgenie/test:latest`) → 31 passed.
- `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` → real `gh`, real decision, `verdict: defers to a
  human — PR is MERGED` (before the fix this command died on the field name).
- `make test-unit`, `make lint`, `make check-docs`, `make check-workflows`,
  `make openspec-validate NAME=auto-merge-gh-json-fields` → results recorded in the PR.
- **The proof the gate works:** the next green PR run's `auto-merge` job is green and lands the PR with no human
  click — the acceptance criterion of #513, and of #482 before it.
