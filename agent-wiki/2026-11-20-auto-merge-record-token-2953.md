# 2026-11-20 — the auto-merge sweep record posts with an issue-capable token (issue #2953, PR #<TBD>)

The sweep recorder landed on main (PR #2951) but every main-head `auto-merge` run then reddened:
its record comment is an ISSUE comment, and the owner PAT behind `secrets.BUMP_TOKEN` cannot
create one. Six `recheck` failures (runs 44658425503, 44658824660, 44658940504, 44659822138,
44661942440, 44664497025, all at main `f71e48e251`) carried
`GraphQL: Resource not accessible by personal access token (addComment)`, and `ci-verdict`
(run 44664498485) answered UNJUDGED RED because of that red check-run. PR-level comments from
the same PAT work; only issue comments are outside its grant.

## What was verified

- `scripts/auto_merge.py recheck` reads a `RECORD_TOKEN` environment variable: when non-empty,
  the `gh issue comment` call for the record runs with `GH_TOKEN` set to that value through the
  environment-only `_gh(token=...)` seam; unset keeps the ambient token byte-identically.
  Tests: `test_record_comment_uses_record_token`,
  `test_record_comment_without_record_token_keeps_the_ambient_token` (the fake gh now captures
  `[issue, GH_TOKEN]` per issue-comment call in `gh.log.record.env`).
- `auto-merge.yml`'s recheck sweep step sets `RECORD_TOKEN: ${{ github.token }}` — the workflow's
  `permissions:` carry `issues: write`, so github-actions[bot] owns the tracker record while the
  merge/approve/PR-comment legs stay on the owner PAT: #874's two-identity doctrine, extended to
  issue comments.
- OpenSpec change `auto-merge-record-token` (validated), capability `sweep-record`, ADDED
  requirement "the sweep record comment is posted with a token allowed to comment on issues".
- Side issue #2954 (labeled blocked): the owner decision on widening `BUMP_TOKEN` to
  `Issues: Write` itself; this lane works around the boundary instead.

## Current status

Branch `feat/auto-merge-record-token-2953`; live proof of the fix is the next main-head
auto-merge run going green and a `github-actions[bot]` `[sweep …]` record landing on #2652 —
recorded in tasks.md when observed.
