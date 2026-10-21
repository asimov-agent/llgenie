# Each bot write runs with the token that can perform it

- Issue: [#430](https://github.com/asimov-agent/llgenie/issues/430)
- OpenSpec change: `bot-pr-token-split`
- Branch: `fix/bot-pr-token-split`

## What was wrong

The PR step ran both of its writes under `GH_TOKEN: ${{ secrets.BUMP_TOKEN }}`: the issue comment that
claims the issue, and `pr create`. The PAT opens a PR (needed, so CI runs on it — #420) but carries no
Issues write, so run 39513850754 created PR #424 and then died with
`GraphQL: Resource not accessible by personal access token (addComment)`. The job was red after the side
effect, the issue looked unclaimed, and no `pr-open` marker was posted.

## What changed

- `scripts/issue_implementer.py` — `_gh(gh, args, token=)` sets `GH_TOKEN` for that child only;
  `pr_token()` reads `PR_TOKEN` (PAT) with the leg's token as fallback; `open_pr()` posts the claim
  comment **first**, then `pr create` with the PAT, then the `pr-open` marker.
- `.github/workflows/issue-bot.yml` — the step carries `GH_TOKEN: ${{ github.token }}` and
  `PR_TOKEN: ${{ secrets.BUMP_TOKEN }}`.
- `tests/test_bot_pr_tokens.py` — a real fake `gh` records the argv **and the token it received**:
  order and per-write token, a denied comment stops before any PR, an unset PAT falls back, and the
  workflow declares both.
- `tests/test_issue_implementer.py` — the two `open_pr` call sites updated (the `_gh` stub takes
  `token=`, and the marker comment is found by its marker rather than by being first).
- `README.md` — which write uses which token, and why.

## Verified

Live, with the real `gh` binary, that a per-call token actually reaches the child:

```
ambient token -> andyholst
per-call token -> refused: (1): gh: Bad credentials (HTTP 401)     # bogus value passed to _gh(…, token=…)
```

- `pytest tests/test_bot_pr_tokens.py tests/test_issue_implementer.py` → 33 passed.
- `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`,
  `make openspec-validate NAME=bot-pr-token-split` — green.

## Notes

- Ordering is part of the fix, not a detail: the write that can be denied now runs before the PR exists,
  so a red run means nothing was half-done.
- The BUMP_TOKEN value itself is never printed or exported by the code; the test uses sentinels.
