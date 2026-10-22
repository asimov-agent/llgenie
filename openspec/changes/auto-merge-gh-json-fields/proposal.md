# The merge decision asks only for fields `gh` has

## Why

The `auto-merge` workflow has never merged anything, and it was never the merge policy's fault. Run
[`39769182946`](https://github.com/asimov-agent/llgenie/actions/runs/39769182946) — PR #511's green run — dies on
its only `gh` call:

```
merge  GH_TOKEN: ***
merge  PR: 511
merge  python3 scripts/auto_merge.py auto-merge --repo "asimov-agent/llgenie" --pr 511 --head-sha 17ada6…
merge  [auto-merge] gh pr view 511 … --json state,isDraft,mergeable,mergeStateStatus,headRefOid,labels,
                  headRepository,author,authorAssociation,reviewDecision failed (1):
                  Unknown JSON field: "authorAssociation"
merge  make: *** [Makefile:734: auto-merge] Error 1
```

`gh pr view --json` has no `authorAssociation` field (the same command on the host, gh `2.102.1`, answers
`Unknown JSON field` and prints its allowlist). `scripts/auto_merge.py::pr_state` asks for it in the single call
every decision is built from, so the run exits 2 **before** `decide()` runs: no merge, no deferral comment, no
verdict.

Measured consequence: **no PR in this repository has ever been auto-merged.** Every recent merge is
`mergedBy=andyholst` (#511, #509, #506, #504, #502, #500, #489, #487, #486, #484, #483, #481), and every
`auto-merge` run in the workflow's history is `failure` or `skipped` — never `success`.

Why CI stayed green on the defect: `tests/test_auto_merge.py`'s fake `gh` returns the JSON blob it was handed and
never validates the requested field NAMES, so a field that does not exist is invisible to the whole unit suite
(issue #513).

## What Changes

- **`PR_VIEW_FIELDS` is one constant**, and `pr_state` joins it into the one `gh pr view --json` call.
  `authorAssociation` is removed; every remaining name is one `gh` lists.
- **Bot detection no longer needs an association field.** `is_bot_login()` decides from the login alone
  (`…[bot]`, `app/…`, `github-actions[bot]`, `app/github-actions`) — the rule #511 introduced for a bot-authored
  PR keeps working without a field that does not exist.
- **The list is locked against `gh`'s own allowlist.** `tests/fixtures/gh-pr-view-fields.json` is captured from
  the real `gh pr view --json __probe__` answer; a unit test asserts every requested field is in it, so the next
  invented field name is a red unit test instead of a silent exit 2 in production.
- **The fake `gh` now enforces that allowlist too**: it refuses an unknown field name exactly the way the real
  CLI does, so every end-to-end case in `tests/test_auto_merge.py` fails on a regression of this class.

## Impact

- The next green PR after this lands is merged by CI with no human click — the gate finally does the job the
  issue that built it asked for (#482).
- A future field-name mistake fails `make test-unit` locally, before it can turn the merge workflow red.
- The trust boundary (#500/#511) is unchanged: owner, write collaborator or bot only, third-party fork heads
  deferred.
