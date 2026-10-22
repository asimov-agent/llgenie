# 2026-10-22 — auto-merge asks `gh pr view` only for fields it has (#513)

## What was wrong

`scripts/auto_merge.py::pr_state` requested `authorAssociation`, which `gh pr view --json` does not have.
`gh` refuses the entire call on an unknown name, so every `auto-merge` run exited 2 before `decide()`; every
recent merge on `main` was made by a human. The fake `gh` in `tests/test_auto_merge.py` returned a fixed JSON
blob and never validated the requested field NAMES, so the unit suite could not see it.

## What changed

- `PR_VIEW_STATE_FIELDS` (the one state call), `PR_VIEW_COMMENT_FIELDS` (deferral dedupe) and their union
  `PR_VIEW_FIELDS` are the only place a `gh pr view` field name is written; `pr_state` and `pr_comments`
  join them into the `--json` argument.
- `authorAssociation` is removed from the request and from the bot-author rule. `_is_bot(login)` decides from
  `author.login` alone (`app/github-actions`, `github-actions[bot]`, any `…[bot]`), and a bot PR still needs
  ACTOR to be the owner, a write collaborator, or a bot.
- `tests/fixtures/gh-pr-view-fields.json` holds the real allowlist captured from
  `gh pr view --json __probe__` (gh 2.102.0, 46 names, command and version recorded).
- New tests: every `PR_VIEW_FIELDS` name is in the fixture; `pr_state`'s `--json` argv is exactly
  `PR_VIEW_STATE_FIELDS`; an App bot and a `[bot]` login are recognised by the login alone.

## Verified

- Full hermetic unit suite: `5040 passed, 6 deselected, 0 failed` in 11m45s — `scripts/unit_tests.py run`
  (the body of the `make test-unit` recipe) on Python 3.11 in the venv the Makefile's host branch uses.
  `make test-unit` itself cannot execute in this container: the Docker daemon cannot unpack image layers
  (`unshare: operation not permitted`), so the `llgenie/test:latest` runner is unavailable.
- `make auto-merge-explain PR=511 REPO=asimov-agent/llgenie` → real `gh`, real verdict
  (`defers to a human — PR is MERGED`); before this change the same command died on the field name.
- `make auto-merge PR=514 REPO=asimov-agent/llgenie DRY=1 ACTOR=andyholst` → real `gh` through the whole
  run path (state, author gate, permission API, decision) on a live open PR, verdict printed, nothing
  merged or commented (dry run).
- `openspec validate auto-merge-gh-view-fields` (CLI 1.10.0, the pin in the Makefile) → "Change
  'auto-merge-gh-view-fields' is valid"; `make openspec-tasks-check NAME=auto-merge-gh-view-fields` → OK.
- `make lint`'s script → `LINT OK`; `make check-docs`, `make check-wiring`, `make check-workflows`,
  `make check-pr-hygiene` green.

Issue: #513. Change: `openspec/changes/auto-merge-gh-view-fields`.
