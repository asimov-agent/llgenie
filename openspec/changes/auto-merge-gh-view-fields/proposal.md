# Ask `gh pr view` only for fields it actually has (issue #513)

## Why

The `auto-merge` workflow has never landed a PR. Run `39769182946` (PR #511, green) shows the only `gh`
call every decision reads:

```
[auto-merge] gh pr view 511 --repo asimov-agent/llgenie --json state,...,author,authorAssociation,reviewDecision failed (1):
             Unknown JSON field: "authorAssociation"
make: *** [Makefile:734: auto-merge] Error 1
```

`authorAssociation` is not a field of `gh pr view --json`. `gh` refuses the whole call on an unknown name
(and prints its allowlist), so `scripts/auto_merge.py::pr_state` exits 2 before `decide()` is reached: no
merge, no deferral comment, and every recent merge on `main` is `mergedBy=andyholst`.

The unit suite could not see it: the fake `gh` in `tests/test_auto_merge.py` answered `pr view` with whatever
JSON blob it was handed and never validated the field NAMES, so a field that does not exist passed every test.

## What Changes

- **`authorAssociation` is gone from the request and from the decision.** The bot-author rule added by #511
  (a bot opener is allowed only when the CI run's actor is the owner, a write collaborator, or the bot) is
  decided from `author.login` alone — a field `gh` has.
- **One constant holds every requested name.** `scripts/auto_merge.py` gains `PR_VIEW_STATE_FIELDS` (the
  single state call the decision reads), `PR_VIEW_COMMENT_FIELDS` (the deferral dedupe) and
  `PR_VIEW_FIELDS` (their union) — the module no longer spells a field list inline.
- **`tests/fixtures/gh-pr-view-fields.json` is the real allowlist.** Captured from the CLI's own
  `gh pr view --json __probe__` answer (gh 2.102.0, 46 names) with its command and version recorded, and a
  unit test asserts every name in `PR_VIEW_FIELDS` is in it — so the next invented field is a red unit test
  instead of a silent exit 2 in production.
- **`pr_state`'s argv is pinned to that constant** by a test that reads the fake `gh`'s recorded argv.
- The bot tests no longer model `authorAssociation` in their state, and a new case proves an App bot
  (`app/github-actions`) and a `…[bot]` login are recognised by the login alone.

## Impact

- The next green, conflict-free PR can be squash-merged by CI with no human click — what #482 built the gate
  for — and a future field-name mistake fails `make test-unit` rather than the merge workflow.
- The trust boundary is unchanged: owner, write collaborator, or bot only; a third-party fork head, a moved
  head, a draft and `do-not-merge` still defer.
